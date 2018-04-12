'''
(*)~---------------------------------------------------------------------------
Copyright (C) 2017-2018  Sander Staal
---------------------------------------------------------------------------~(*)
'''

import cv2
import numpy as np
import time
import colorsys
import audio
import logging

from methods import normalize
from pyglui.cygl.utils import draw_points_norm, draw_polyline, RGBA, draw_rounded_rect
from OpenGL.GL import GL_POLYGON
from .. finish_calibration import finish_calibration
from . finger_detection import Finger_Detection
from glfw import GLFW_PRESS
from pyglui import ui
from .. calibration_plugin_base import Calibration_Plugin

logger = logging.getLogger(__name__)

class Finger_Calibration(Calibration_Plugin):

    def __init__(self, g_pool):
        super().__init__(g_pool)
        self.detected = False
        self.pos = None
        self.smooth_pos = 0.,0.
        self.smooth_vel = 0.
        self.sample_site = (-2,-2)
        self.counter = 0
        self.counter_max = 30
        self.markers = []
        self.show_contour = True
        self.contour = []
        self.world_size = None

        self.static_finger = True
        self.correct_finger_scale = 25

        self.color_h = 20
        self.color_s = 36
        self.color_v = 62
        self.color_tolerance_h = 20
        self.color_tolerance_s = 24
        self.color_tolerance_v = 38

        self.clicked_color_point = None
        self.can_click_for_color = False

        self.finger_log_enabled = False
        self.finger_log = []
        self.first_sample = True
        self.start_time = 0
        self.end_time = 0

        self.menu = None

    def init_ui(self):
        super().init_ui()
        self.menu.label = "Finger Calibration"
        self.menu.append(ui.Info_Text("Use the tip of your finger to calibrate the eye tracker."))
        self.menu.append(ui.Slider('counter_max',self,step=1, min=1, max=50, label='Number of samples'))
        self.menu.append(ui.Switch('static_finger',self,label='Use static fingers'))
        self.menu.append(ui.Slider('correct_finger_scale',self,step=1, min=0, max=60, label='Finger correction scale'))
        self.menu.append(ui.Switch('show_contour',self,label='Show contour lines'))
        self.menu.append(ui.Switch('finger_log_enabled',self,label='Log finger calibration points'))

        self.menu.append(ui.Info_Text("Choose HSV color threshold for hand segmentation:"))
        self.menu.append(ui.Button('Click to choose color', self.show_click_infotext))

        self.menu.append(ui.Slider('color_h',self,step=1, min=0, max=360, label='Hue'))
        self.menu.append(ui.Slider('color_s',self,step=1, min=0, max=100, label='Saturation'))
        self.menu.append(ui.Slider('color_v',self,step=1, min=0, max=100, label='Value'))

        self.menu.append(ui.Button('Set to default handskin', self.set_to_handskin_color))
        self.menu.append(ui.Button('Set to default red glove', self.set_to_glove_color))

        self.menu.append(ui.Info_Text("Set tolerance range for individual color channels:"))
        self.menu.append(ui.Slider('color_tolerance_h',self,step=1, min=0, max=35, label='Range Hue'))
        self.menu.append(ui.Slider('color_tolerance_s',self,step=1, min=0, max=100, label='Range Saturation'))
        self.menu.append(ui.Slider('color_tolerance_v',self,step=1, min=0, max=100, label='Range Value'))

    def start(self):
        super().start()
        audio.say("Starting {}".format(self.mode_pretty))
        logger.info("Starting {}".format(self.mode_pretty))

        self.finger_log = []
        self.start_time = 0
        self.end_time = 0
        self.first_sample = True

        self.clicked_color_point = None
        self.can_click_for_color = False

        self.active = True
        self.ref_list = []
        self.pupil_list = []

    def stop(self):
        audio.say("Stopping  {}".format(self.mode_pretty))
        logger.info('Stopping  {}'.format(self.mode_pretty))
        self.screen_marker_state = 0
        self.active = False
        self.button.status_text = ''

        logger.info("Calibration took {} seconds.".format(self.end_time - self.start_time))

        if self.mode == 'calibration':
            # Store array of logged finger positions to a file
            if self.finger_log_enabled:
                file = open('finger_calibration_points_'+time.strftime('%Y-%m-%d_%H:%M:%S', time.gmtime())+'.txt', 'w')
                file.write('\n'.join(str(e[0]) for e in self.finger_log))
                file.close()
            finish_calibration(self.g_pool, self.pupil_list, self.ref_list)
        elif self.mode == 'accuracy_test':
            if self.finger_log_enabled:
                file = open('finger_accuracy_test_points_'+time.strftime('%Y-%m-%d_%H:%M:%S', time.gmtime())+'.txt', 'w')
                file.write('\n'.join(str(e[0]) for e in self.finger_log))
                file.close()
            self.finish_accuracy_test(self.pupil_list, self.ref_list)
        super().stop()

    def show_click_infotext(self):
        logger.debug("Click in the frame to extract the color from that pixel")
        self.can_click_for_color = True

    def set_to_handskin_color(self):
        '''
        Sets the threshold to handskin color
        '''
        self.color_h = 20
        self.color_s = 36
        self.color_v = 62
        self.color_tolerance_h = 20
        self.color_tolerance_s = 24
        self.color_tolerance_v = 38

    def set_to_glove_color(self):
        '''
        Sets the threshold to red
        '''
        self.color_h = 0
        self.color_s = 60
        self.color_v = 60
        self.color_tolerance_h = 20
        self.color_tolerance_s = 40
        self.color_tolerance_v = 40

    def on_notify(self, notification):
        '''
        Reacts to notifications:
           ``calibration.should_start``: Starts the calibration procedure
           ``calibration.should_stop``: Stops the calibration procedure

        Emits notifications:
            ``calibration.started``: Calibration procedure started
            ``calibration.stopped``: Calibration procedure stopped
            ``calibration.marker_found``: Steady marker found
            ``calibration.marker_moved_too_quickly``: Marker moved too quickly
            ``calibration.marker_sample_completed``: Enough data points sampled

        '''
        super().on_notify(notification)

    def recent_events(self, events):
        """
        gets called once every frame.
        reference positon need to be published to shared_pos
        if no reference was found, publish 0,0
        """
        frame = events.get('frame')

        if frame:
            self.world_size = frame.width,frame.height
            
            # Check if user selected a new color as threshold
            if self.clicked_color_point is not None:
                pnt = [int(self.clicked_color_point[0][0]), int(self.clicked_color_point[0][1])]

                bgr_color = frame.img[pnt[1]][pnt[0]];
                extracted_color = colorsys.rgb_to_hsv(bgr_color[2]/255, bgr_color[1]/255, bgr_color[0]/255)
                self.color_h = int(extracted_color[0]*360)
                self.color_s = int(extracted_color[1]*100)
                self.color_v = int(extracted_color[2]*100)

                self.clicked_color_point = None

        if self.active and frame:
            recent_pupil_positions = events['pupil_positions']

            # Normalize HSV color specs to OpenCV HSV color specs
            color_threshold = [self.color_h/2, self.color_s * 2.55, self.color_v * 2.55, self.color_tolerance_h/2, self.color_tolerance_s * 2.55, self.color_tolerance_v * 2.55]

            # Detect fingertips
            res = Finger_Detection.findFingers(frame.img, 30, color_threshold, self.correct_finger_scale)
            fingers = res[0]
            self.contour = res[1]

            # Only update finger positions if we aren't currently collecting data points (if static fingers enabled)
            if self.counter <= 0 or not self.static_finger:
                self.markers = fingers

            # Detected single fingertip
            if len(self.markers) == 1:
                self.detected = True
                marker_pos = [float(self.markers[0][0]), float(self.markers[0][1])]

                self.pos = normalize(marker_pos, (frame.width,frame.height),flip_y=True)
            else:
                self.detected = False
                self.pos = None  # indicate that no reference is detected
            
            # Tracking logic
            # Code copied from Pupil's manual marker plugin implementation
            if self.detected:
                # calculate smoothed manhattan velocity
                smoother = 0.3
                smooth_pos = np.array(self.smooth_pos)
                pos = np.array(self.pos)
                new_smooth_pos = smooth_pos + smoother*(pos-smooth_pos)
                smooth_vel_vec = new_smooth_pos - smooth_pos
                smooth_pos = new_smooth_pos
                self.smooth_pos = list(smooth_pos)
                #manhattan distance for velocity
                new_vel = abs(smooth_vel_vec[0])+abs(smooth_vel_vec[1])
                self.smooth_vel = self.smooth_vel + smoother*(new_vel-self.smooth_vel)

                #distance to last sampled site
                sample_ref_dist = smooth_pos-np.array(self.sample_site)
                sample_ref_dist = abs(sample_ref_dist[0])+abs(sample_ref_dist[1])

                # start counter if ref is resting in place and not at last sample site
                if self.counter <= 0:
                    if self.smooth_vel < 0.01 and sample_ref_dist > 0.1:
                        self.sample_site = self.smooth_pos
                        audio.beep()
                        self.end_time = time.time()
                        if self.first_sample:
                            self.first_sample = False
                            self.start_time = time.time()

                        logger.debug("Steady marker found. Starting to sample {} datapoints".format(self.counter_max))
                        self.notify_all({'subject':'calibration.marker_found','timestamp':self.g_pool.get_timestamp(),'record':True})
                        self.counter = self.counter_max
                        self.finger_log.append(self.markers)

                if self.counter > 0:
                    if self.smooth_vel > 0.01:
                        audio.tink()
                        self.end_time = time.time()
                        logger.warning("Marker moved too quickly: Sampled {} datapoints. Looking for steady marker again.".format(self.counter_max-self.counter))
                        self.notify_all({'subject':'calibration.marker_moved_too_quickly','timestamp':self.g_pool.get_timestamp(),'record':True})
                        self.counter = 0
                    else:
                        self.counter -= 1
                        ref = {}
                        ref["norm_pos"] = self.pos
                        ref["screen_pos"] = marker_pos
                        ref["timestamp"] = frame.timestamp
                        self.ref_list.append(ref)

                        if events.get('fixations', []):
                            self.counter -= 5
                        if self.counter <= 0:
                            #last sample before counter done and moving on
                            audio.tink()
                            self.end_time = time.time()
                            logger.info("Sampled {} datapoints. Stopping to sample. Looking for steady marker again.".format(self.counter_max))
                            self.notify_all({'subject':'calibration.marker_sample_completed','timestamp':self.g_pool.get_timestamp(),'record':True})

            #always save pupil positions
            for p_pt in recent_pupil_positions:
                if p_pt['confidence'] > self.pupil_confidence_threshold:
                    self.pupil_list.append(p_pt)

            if self.counter <= 0:
                self.button.status_text = 'Looking for Marker'
            elif self.counter > 0:
                self.button.status_text = 'Sampling Data'
        else:
            pass


    def gl_display(self):
        """
        use gl calls to render
        at least:
            the published position of the reference
        better:
            show the detected postion even if not published
        """

        # Draw rectangle preview with threshold color
        if self.world_size:
            offset = self.world_size[0]/130.0
            ratio = self.world_size[1]/self.world_size[0]

            rect_size = None
            if ratio == 0.75:
                rect_size = [(self.world_size[0]/20.0), self.world_size[0]/20.0  * 1.3]
            else:
                rect_size = [(self.world_size[0]/20.0), self.world_size[0]/20.0  * 1.0]

            rect_color = colorsys.hsv_to_rgb(self.color_h/360, self.color_s/100, self.color_v/100)
            draw_rounded_rect([offset, self.world_size[1] - rect_size[1] - offset], size = rect_size, corner_radius = offset/2, color=RGBA(rect_color[0], rect_color[1], rect_color[2], 1.))

        if self.active:

            # Draw contour of hand
            if self.show_contour:
                con = [(c[0][0], c[0][1]) for c in self.contour]
                if len(con) > 2:
                    con.append(con[0])
                    draw_polyline(con, color=RGBA(0.,1.,0.,.7), thickness=5.0)

            # Draw all detected fingertips
            if len(self.markers) == 1:
                marker_norm = normalize(self.markers[0], (self.world_size[0],self.world_size[1]), flip_y=True)
                draw_points_norm([marker_norm], size=30, color=RGBA(0.,1.,1.,.5))
            else:
                for mark in self.markers:
                    marker_norm = normalize(mark, (self.world_size[0],self.world_size[1]), flip_y=True)
                    draw_points_norm([marker_norm], size=30, color=RGBA(0.,0.,1.,.5))


    def on_click(self, pos, button, action):
        # User pressed on frame to select new threshold color
        if action == GLFW_PRESS and self.can_click_for_color:
            self.clicked_color_point = np.array([pos], dtype=np.float32)
            self.can_click_for_color = False


    def deinit_ui(self):
        """gets called when the plugin get terminated.
        This happens either voluntarily or forced.
        if you have an atb bar or glfw window destroy it here.
        """
        if self.active:
            self.stop()
        super().deinit_ui()
