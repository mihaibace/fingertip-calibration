'''
(*)~---------------------------------------------------------------------------
Copyright (C) 2017-2018  Sander Staal
---------------------------------------------------------------------------~(*)
'''

import cv2
import numpy as np
import copy
import math
import time

from . disjoint_set import DisjointSet

# parameters
BLUR_VALUE = 7
NEIGHBORHOOD_SIZE = 50
LOWER_CUT_PERCENTAGE = 0.3 # Doesn't consider the 30% lowest parts of the contour as fingertips (results in less false positives)
DILATION_SIZE = 5

class Finger_Detection():

    '''
    Calculate distance between two points
    '''
    def ptDist(u, v):
        return np.sqrt((u - v).dot((u - v)))

    '''
    Extract foreground from background by thresholding the color
    Colors need to be normalized to OpenCVs HSV norm (e.g., h is between 0 and 180)
    '''
    def removeBG(frame, segmentation_color):
        # change the color space
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        h = segmentation_color[0]
        s = segmentation_color[1]
        v = segmentation_color[2]
        tolerance_h = segmentation_color[3]
        tolerance_s = segmentation_color[4]
        tolerance_v = segmentation_color[5]

        # define range for hand color in HSV
        mask = 0

        if h >= tolerance_h and (h+tolerance_h) <= 180:
            # E.g. h=50 and tolerance_h=10 -> valid range is [40, 60]
            mask = cv2.inRange(hsv, np.array([h - tolerance_h, s - tolerance_s, v - tolerance_v]), np.array([h + tolerance_h, s + tolerance_s, v + tolerance_v]))
        elif h < tolerance_h:
            # E.g. h=10 and tolerance_h=20 -> valid range is [350, 360] and [0,30]
            mask_temp1 = cv2.inRange(hsv, np.array([0, s - tolerance_s, v - tolerance_v]), np.array([h + tolerance_h, s + tolerance_s, v + tolerance_v]))
            mask_temp2 = cv2.inRange(hsv, np.array([180 - (tolerance_h - h), s - tolerance_s, v - tolerance_v]), np.array([180, s + tolerance_s, v + tolerance_v]))
            mask = cv2.addWeighted(mask_temp1, 1.0, mask_temp2, 1.0, 0.0)
        else:
            # E.g. h=350 and tolerance_h=20 -> valid range is [330, 360] and [0,10]
            mask_temp1 = cv2.inRange(hsv, np.array([h - tolerance_h, s - tolerance_s, v - tolerance_v]), np.array([180, s + tolerance_s, v + tolerance_v]))
            mask_temp2 = cv2.inRange(hsv, np.array([0, s - tolerance_s, v - tolerance_v]), np.array([0 + (h+tolerance_h-180), s + tolerance_s, v + tolerance_v]))
            mask = cv2.addWeighted(mask_temp1, 1.0, mask_temp2, 1.0, 0.0)

        # Remove noise in mask
        mask = cv2.medianBlur(mask, DILATION_SIZE)
        mask = cv2.dilate(mask, np.ones((DILATION_SIZE, DILATION_SIZE), np.uint8))

        result = cv2.bitwise_and(frame, frame, mask=mask)
        return tuple([result, mask])

    '''
    Group hull points (which are in the same region) together
    '''
    def getHullPoints(res, maxDist):
        hull = cv2.convexHull(res, returnPoints=False)   

        # Group all points in local neighborhood
        disj_set = DisjointSet(range(len(hull)))
        for u in range(0, len(hull)):
            for v in range(u+1, len(hull)):
                pnt_u = res[hull[u][0]][0]
                pnt_v = res[hull[v][0]][0]

                if Finger_Detection.ptDist(pnt_u, pnt_v) <= maxDist:
                    disj_set.union(u, v)

        neighborhoods = disj_set.get()
        points = []

        # Map points in local neighborhood to most central point
        for i in range(len(neighborhoods)):
            center = [0, 0]
            
            # Find center
            for j in range(len(neighborhoods[i])):
                pntIndex = neighborhoods[i][j]
                pnt = res[hull[pntIndex][0]][0]

                center[0] += pnt[0]
                center[1] += pnt[1]

            center[0] = center[0]/len(neighborhoods[i])
            center[1] = center[1]/len(neighborhoods[i])

            closestPnt = [0, 0]
            closestDst = math.inf

            # Find point closest to center
            for j in range(len(neighborhoods[i])):
                pntIndex = neighborhoods[i][j]
                pnt = res[hull[pntIndex][0]][0]

                if Finger_Detection.ptDist(pnt, center) < closestDst:
                    closestDst = Finger_Detection.ptDist(pnt, center)
                    closestPnt = hull[pntIndex][0]

            points.append(closestPnt)

        return np.array(points)

    '''
    Returns vector which points in the same direction as the finger
    '''
    def getCorrectionVector(pnt, d1, d2, angle):
        angle = angle * (math.pi / 180)

        # Rotate d1 counterclockwise by angle/2 around pnt
        qx = pnt[0] + math.cos(angle/2) * (d1[0] - pnt[0]) - math.sin(angle/2) * (d1[1] - pnt[1])
        qy = pnt[1] + math.sin(angle/2) * (d1[0] - pnt[0]) + math.cos(angle/2) * (d1[1] - pnt[1])

        q = [qx, qy]

        if Finger_Detection.ptDist(d2, q) > Finger_Detection.ptDist(d2, d1):
           # Rotated in wrong direction, rotate by taking the other point d2
           qx = pnt[0] + math.cos(angle/2) * (d2[0] - pnt[0]) - math.sin(angle/2) * (d2[1] - pnt[1])
           qy = pnt[1] + math.sin(angle/2) * (d2[0] - pnt[0]) + math.cos(angle/2) * (d2[1] - pnt[1])

           q = [qx, qy]      

        # Get line equation of the rotated point and pnt
        line = q - pnt
        magnitude = np.sqrt(line.dot(line))
        line = line/magnitude

        return line

    '''
    Detects fingers in a given contour
    '''
    def detectFingers(res, finger_correction_scale):
        hull = Finger_Detection.getHullPoints(res, NEIGHBORHOOD_SIZE)
        fingerTips = []

        defects = cv2.convexityDefects(res, hull)

        if type(defects) != type(None):

            # Get neighboring defect points of each hull point
            defectNeighbors = {}
            for i in range(defects.shape[0]):
                s, e, f, _ = defects[i][0]
                
                if s in defectNeighbors:
                    defectNeighbors[s].append(f)
                else:
                    defectNeighbors[s] = [f]

                if e in defectNeighbors:
                    defectNeighbors[e].append(f)
                else:
                    defectNeighbors[e] = [f]

            # Get point with highest and lowest y coordinate
            extTop = tuple(res[res[:, :, 1].argmin()][0])
            extBottom = tuple(res[res[:, :, 1].argmax()][0])
            
            # Filter out any points which are in the lowest LOWER_CUT_PERCENTAGE %
            height = extTop[1] - extBottom[1]
            height_threshold = extBottom[1] + int(LOWER_CUT_PERCENTAGE * height)

            for pntIndex, defecIndices in defectNeighbors.items():

                # Only consider hull points that have 2 neighbor defects
                if len(defecIndices) == 2:
                    pnt = res[pntIndex][0]
                    d1 = res[defecIndices[0]][0]
                    d2 = res[defecIndices[1]][0]

                    a = Finger_Detection.ptDist(d1, d2)
                    b = Finger_Detection.ptDist(pnt, d1)
                    c = Finger_Detection.ptDist(pnt, d2)

                    if pnt[1] > height_threshold:
                        continue
                    
                    # Fingertip points are those which have a sharp angle to its defect points
                    term = (b ** 2 + c ** 2 - a ** 2) / (2 * b * c)
                    angle = math.acos(min(1, max(-1, term))) * (180 / math.pi)

                    # angle less than 60 degree, treat as fingers
                    if angle <= 60:
                        # Shift the point towards the inside of the finger
                        line = Finger_Detection.getCorrectionVector(pnt, d1, d2, angle)    
                        tip = pnt + [int(line[0]*finger_correction_scale), int(line[1]*finger_correction_scale)]

                        fingerTips.append([tip[0], tip[1]])
        return fingerTips

    '''
    Returns the positions of finger tips in a given frame
    '''
    def findFingers(frame, threshold, segmentation_color, finger_correction_scale):
        res = Finger_Detection.removeBG(frame, segmentation_color)
        img = res[0]
        mask = res[1]

        # Remove noise
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (BLUR_VALUE, BLUR_VALUE), 0)
        _, thresholded = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY)

        # get the coutours
        _, contours, hierarchy = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        length = len(contours)
        maxArea = -1

        fingers = []

        if length > 0:
            # Find the biggest contour (according to area)
            for i in range(length):  
                temp = contours[i]
                area = cv2.contourArea(temp)
                if area > maxArea:
                    maxArea = area
                    ci = i

            res = contours[ci]
            hull = cv2.convexHull(res)

            fingers = Finger_Detection.detectFingers(res, finger_correction_scale)

        return (fingers, res)
