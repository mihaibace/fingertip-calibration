# Fingertip Calibration Plugin

# Installation

To install the fingertip calibration plugin, follow the instructions described at the [Pupil docs][docs] and install all dependencies for the system to run the Pupil software from code. 


After all dependencies have been installed, the [GitHub repository][rep] needs to be cloned from Pupil and the user has to navigate to the following directory:

```
/git_folder_of_pupil/pupil_src/shared_modules/calibration_routines/
```

If the above folder does not exist, run Pupil Capture once and close it again. Afterwards, the user can copy the here provided directory `finger_detection`, which contains the fingertip calibration plugin, into the above directory. 

Now the user needs to edit the following pupil file

```
/git_folder_of_pupil/pupil_src/shared_modules/calibration_routines/__init__.py
```

and add the following import

`
from . finger_detection . finger_calibration import Finger_Calibration
`

and add the following element to the `calibration_plugins` list:

`
Finger_Calibration
`

The final `__init__.py` file should now look similar to this:

```
from . finger_detection . finger_calibration import Finger_Calibration
from . screen_marker_calibration import Screen_Marker_Calibration
from . manual_marker_calibration import Manual_Marker_Calibration
from . fingertip_calibration import Fingertip_Calibration
from . single_marker_calibration import Single_Marker_Calibration
from . natural_features_calibration import Natural_Features_Calibration
from . hmd_calibration import HMD_Calibration, HMD_Calibration_3D
from . gaze_mappers import Gaze_Mapping_Plugin, Dummy_Gaze_Mapper, Monocular_Gaze_Mapper, Binocular_Gaze_Mapper, Vector_Gaze_Mapper, Binocular_Vector_Gaze_Mapper, Dual_Monocular_Gaze_Mapper
from . calibration_plugin_base import Calibration_Plugin

calibration_plugins = [Finger_Calibration,
                       Screen_Marker_Calibration,
                       Manual_Marker_Calibration,
                       Fingertip_Calibration,
                       Single_Marker_Calibration,
                       Natural_Features_Calibration,
                       HMD_Calibration,
                       HMD_Calibration_3D]

gaze_mapping_plugins = [Dummy_Gaze_Mapper,
                        Monocular_Gaze_Mapper,
                        Vector_Gaze_Mapper,
                        Binocular_Gaze_Mapper,
                        Binocular_Vector_Gaze_Mapper,
Dual_Monocular_Gaze_Mapper]
```


Now, the Pupil Capture software can be started and the plugin will automatically be detected and show up in the *Calibration Method* drop down menu as `Finger Calibration`.

[docs]: <https://docs.pupil-labs.com/#developer-docs>
[rep]: <https://github.com/pupil-labs/pupil>

This plugin has successfully been tested on Pupil Capture 1.6.24

# User Manual

To calibrate the eye tracker, press "C" to start the calibration. Afterwards, hold the hand and fingertip in the scene camera's field of view and fixate the tip of your finger. Once the system detects the fingertip, it will automatically output an audio feedback to let the user know that multiple sample points are being collected from that specific location. A second sound will inform the user that the sampling process has finished. You can then move the fingertip to the next location and start sampling the next set of calibration samples. If you have collected enough fixation locations, simply press again "C" to stop the calibration process.

## Settings

There are various settings which can be fine-tuned to optimize the performance of the calibration method:

##### Number of Samples
Sets the number of samples which are subsequently collected for each detected fingertip location in the scene. The number can range from 1 to 50 samples (default value is 30).

##### Use Static Fingers
If activated, the plugin assumes that the fixation point doesn't change during the sampling. This means that only the first frame, in which the fingertip is detected, matters. All subsequent samples which are collected for this fixation point assume that the fingertip is still located at the initial position. This method is more robust in cases of (unconscious) finger movements or fingertip detection problems (since the fingertip only needs to be detected in one frame per location).

##### Finger Correction Scale
Sets the translation factor in which the convex hull points are corrected towards the center of the finger (in pixels). If set to 0, the fingertips are located at the edges of the finger. This value ranges between 0 and 70 pixels.

##### Show Contour Lines
If enabled, the plugin shows the contour line (in green) of the detected hand in the scene camera preview window. This is done by selecting the hand skin-color segmentation with the largest area.

##### Log Finger Calibration Points
Sets whether the plugin should log the detected fingertip locations from the scene camera view. If enabled, the plugin logs the x and y coordinates (in pixels) and stores them in a separate file in the `pupil_src` directory. Works for both, calibration and accuracy test.

#### Fine-Tuning the Hand Segmentation
The user can provide his own handskin color threshold by selecting his own reference values for the three HSV color channels. A preview of the currently selected color in the HSV color space is shown by the window in the bottom left corner of the world camera frame.

Furthermore, the user can select his own tolerance range for the individual HSV color channels with the parameters "Range Hue", "Range Saturation" and "Range Value". If the user, for example, has chosen a hue value of 20° and a range hue of 10°, then all hue values between 20° +/- 10° (i.e., in the range of 10° and 30°) are considered as valid handskin color hue values. We recommend to do this kind fine tuning after the user has pressed "C" and has enabled the "Show Contour Lines" option, to get a immediate live feedback of how well the current settings work.

##### Click to choose color
When pressing this button, the user can extract the pixel color from the scene camera preview window by clicking with the mouse on it. The plugin will then automatically read out the HSV color values from this pixel. The HSV tolerance ranges keep their value.

##### Set to default handskin 
If pressed, the HSV color channels and the tolerance ranges will automatically be set to values which can detect white hand skin colors. This option is a good starting point for users who want to use the calibration plugin for the first time.

##### Set to default red glove
If pressed, the HSV color channels and the tolerance ranges will automatically be set to values which can detect strong red colors. This option is suitable for user who wear a red glove.