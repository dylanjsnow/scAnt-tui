import gphoto2 as gp
import time
import logging
import locale
import os

from PIL import Image
import imageio
import io
import rawpy


print('Please connect and switch on your camera')
error, camera = gp.gp_camera_new()
while True:
    error = gp.gp_camera_init(camera)
    if error >= gp.GP_OK:
        # operation completed successfully so exit loop
        break
    if error != gp.GP_ERROR_MODEL_NOT_FOUND:
        # some other error we can't handle here
        raise gp.GPhoto2Error(error)
    # no camera, try again in 2 seconds
    time.sleep(2)
# continue with rest of program
print("Camera connected")

locale.setlocale(locale.LC_ALL, '')
logging.basicConfig(format='%(levelname)s: %(name)s: %(message)s', level=logging.WARNING)
callback_obj = gp.check_result(gp.use_python_logging())
camera = gp.Camera()
camera.init()
print('Capturing image')
file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
print('Camera file path: {0}/{1}'.format(file_path.folder, file_path.name))
target = os.path.join('.', file_path.name)
print('Copying image to computer: ', target)
camera_file = camera.file_get(file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL)
camera_file.save(target)

print("Change the settings of the camera capture")
print('Checking camera config')
print("get configuration tree")
config = gp.check_result(gp.gp_camera_get_config(camera))
print("find the image format config item")
print("camera dependent - 'imageformat' is 'imagequality' on some")
OK, image_format = gp.gp_widget_get_child_by_name(config, 'imageformat')
if OK >= gp.GP_OK:
    print("Get current setting")
    value = gp.check_result(gp.gp_widget_get_value(image_format))
    print("Current image format: ", value)
    if 'raw' in value.lower():
        print('Cannot preview raw images, have to convert first')
        with rawpy.imread(target) as raw:
            rgb = raw.postprocess(rawpy.Params(use_camera_wb=True))
        print('Saving image')
        imageio.imsave('rawpy.jpg', rgb)
print("find the capture size class config item")
print("need to set this on my Canon 350d to get preview to work at all")
OK, capture_size_class = gp.gp_widget_get_child_by_name(
    config, 'capturesizeclass')
if OK >= gp.GP_OK:
    print("set value of capture size class")
    value = gp.check_result(gp.gp_widget_get_choice(capture_size_class, 2))
    gp.check_result(gp.gp_widget_set_value(capture_size_class, value))
    print("set config")
    gp.check_result(gp.gp_camera_set_config(camera, config))
print("capture preview image (not saved to camera memory card)")
print('Capturing preview image')
camera_file = gp.check_result(gp.gp_camera_capture_preview(camera))
file_data = gp.check_result(gp.gp_file_get_data_and_size(camera_file))
print("display image using Pillow")
data = memoryview(file_data)
print(type(data), len(data))
print(data[:10].tolist())
image = Image.open(io.BytesIO(file_data))
image.show()

# Convert the raw Canon .cr3 file to a .jpg file
# https://askubuntu.com/questions/1039259/how-to-convert-cr3-raw-files-to-jpg

camera.exit()