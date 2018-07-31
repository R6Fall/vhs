import math
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw
from config import basedir


class ImageObject:
    is_display = False
    is_number = False

    def __init__(self, contour, id):
        self.id = id
        self.contour = contour
        self.rect = cv2.minAreaRect(contour)
        self.box = np.int0(cv2.boxPoints(self.rect))
        self.min_x = np.ndarray.min(self.box[..., 0])
        self.max_x = np.ndarray.max(self.box[..., 0])
        self.min_y = np.ndarray.min(self.box[..., 1])
        self.max_y = np.ndarray.max(self.box[..., 1])

    def find_relation(self, image_objects):
        for image_object in image_objects:
            if (self.min_x < image_object.min_x < self.max_x) and (self.min_y < image_object.min_y < self.max_y):
                self.is_display = True
                self.relation = image_object.id
                image_object.is_number = True
                image_object.relation = self.id

    @staticmethod
    def identify(display, mask, img):
        pass


class Screen:
    def __init__(self, width, height, left=0, top=0):
        self.width = width
        self.height = height
        self.left = left
        self.top = top

    def get_formatted_screen(self, picture_size):
        width = self.width
        height = self.height
        if (width / height) > picture_size:
            height = int(1 / picture_size * width)
        elif (width / height) < picture_size:
            width = int(picture_size * height)
        left = (self.width - width) // 2
        top = (self.height - height) // 2
        return Screen(width, height, left, top)

    def get_device_screen(self, rect):
        if -95 < rect[2] < -85:
            firsty = int(rect[0][1] - rect[1][0] / 2) - self.top
            firstx = int(rect[0][0] - rect[1][1] / 2) - self.left
            lastx = int(rect[0][0] + rect[1][1] / 2) - self.left
        else:
            firsty = int(rect[0][1] - rect[1][1] / 2) - self.top
            firstx = int(rect[0][0] - rect[1][0] / 2) - self.left
            lastx = int(rect[0][0] + rect[1][0] / 2) - self.left
        scale = (self.width / (lastx - firstx)) * 100
        left = - (firstx / self.width) * scale
        top = - (firsty / self.height) * scale
        device_screen = Screen(lastx - firstx, None, left, top)
        device_screen.scale = scale
        return device_screen


class CalibrationImage:
    img_save_path = 'images/calibrate/'

    def __init__(self, impath, device_amount):
        self.impath = impath
        self.device_amount = device_amount
        self.img = cv2.imread(self.impath)

    def __image_converting(self):
        """
        Method of converting and transforming an original image
        """
        cv2.imwrite(self.img_save_path + 'img_non_hsv' + '.png', self.img)
        self.img = cv2.medianBlur(self.img, 5)
        cv2.imwrite(self.img_save_path + 'img_medianBlur' + '.png', self.img)
        self.img = cv2.cvtColor(self.img, cv2.COLOR_BGR2HSV)
        cv2.imwrite(self.img_save_path + 'img_hsv' + '.png', self.img)

    def __create_mask(self):
        """
        Method for creating an image mask
        """
        lower_cyan = np.array((170, 175, 175), np.uint8)
        print('lower_red: ', lower_cyan)
        upper_cyan = np.array((190, 255, 255), np.uint8)
        print('upper_red: ', upper_cyan)
        self.mask = cv2.inRange(self.img, lower_cyan, upper_cyan)
        cv2.imwrite(self.img_save_path + 'mask' + '.png', self.mask)

    def find_contours(self):
        """
        Method for finding contours on image
        :return: Contours found on image
        """
        self.__image_converting()
        self.__create_mask()
        _, contours, hierarchy = cv2.findContours(self.mask, cv2.RETR_TREE,
                                                  cv2.CHAIN_APPROX_NONE)
        self.contours = sorted(contours, key=lambda x: len(x))[-self.device_amount * 2:]
        print('contours: ', self.contours)
        return self.contours


class Map:

    @classmethod
    def draw_map(cls, draw, rect, color):
        """
        Method for draw one of displays on map
        # :param draw: PIL draw variable
        :param rect: Coordinates of drawing display
        :param color: Display color
        """
        draw.polygon(np.int0(cv2.boxPoints(rect)).flatten().tolist(), fill=color)

    @classmethod
    def create_map(cls, final_screen):
        """
        Method for initializing the device map
        :param final_screen: Final screen
        :return: Blank room map image
        """
        room_map = Image.new('RGB', [final_screen.width, final_screen.height], (255, 255, 255))
        return ImageDraw.Draw(room_map), room_map

    @classmethod
    def save_map(cls, draw, room, room_map):
        """
        Method for save complete room map
        :param draw: PIL draw variable
        :param room: Id of room
        :param room_map: Complete room map image
        """
        del draw
        filename = basedir + '/images/' + str(room.id) + '_map.jpg'
        if os.path.exists(filename):
            os.remove(filename)
        room_map.save(filename)


class Parser:
    def __init__(self, room, devices, impath):
        self.room = room
        self.devices = devices
        self.impath = impath

    @property
    def parse(self):
        """
        Main parser controller method
        :return: Successful / unsuccessful parsing
        """
        device_amount, image_objects, items = self.__variables_initialise(self.devices)

        img_class = CalibrationImage(self.impath, device_amount)

        contours = img_class.find_contours()

        maxX, maxY, minX, minY = self.__contour_calculation(contours, image_objects)

        for image_object in image_objects:
            image_object.find_relation(image_objects)

            print(image_object.rect)

        displays = sorted(image_objects, key=lambda x: x.is_display)[-device_amount:]

        print('displays: ', displays)

        self.__displays_append(self.devices, displays, items)

        print('items: ', items)

        self.__handle_parse(items, minX, minY, maxX, maxY)

        is_parsed = True

        return is_parsed

    def __handle_parse(self, items, minX, minY, maxX, maxY):
        """
        A method that processes the search result of devices in the image and
         controls the process of drawing the device map.
        :param items: list of all identified devices
        :param minX: minimal x of screen
        :param minY: minimal y of screen
        :param maxX: maximal x of screen
        :param maxY: maximal y of screen
        """
        trimmed_screen = Screen(maxX - minX, maxY - minY)
        final_screen = trimmed_screen.get_formatted_screen(16 / 9)
        draw, room_map = Map.create_map(final_screen)
        for item in items:
            device, display = item
            display.rect = ((display.rect[0][0] - minX, display.rect[0][1] - minY), display.rect[1], display.rect[2])
            device_screen = final_screen.get_device_screen(display.rect)
            device.save_screen_params(device_screen)
            Map.draw_map(draw, display.rect, (255, 0, 0))

        Map.save_map(draw, self.room, room_map)

    @classmethod
    def __variables_initialise(cls, devices):
        """
        Method for initializing variables
        :param devices: List of devices in the room
        :return: Number of member devices, empty list of objects on image, empty items list
        """
        device_amount = len(devices)  # TODO take device amount on calibrate pic
        print('device amount: ', device_amount)
        image_objects = []
        items = list()
        return device_amount, image_objects, items

    @classmethod
    def __displays_append(cls, devices, displays, items):
        """
        Method appends list of items
        :param devices: List of devices in the room
        :param displays: Sorted list of devices found on image
        :param items: empty items list
        """
        for display in displays:
            print('rect: ', display.rect)

            for device in devices:
                items.append([device, display])
                break

    @classmethod
    def __contour_calculation(cls, contours, image_objects):
        """
        Method of controlling calculation contours for forming the final image
        :param contours: Contours found in the image
        :param image_objects: Objects found in the image
        :return:  minimal & maximum x & y of screen
        """
        i = 0
        maxX = maxY = -math.inf
        minY = minX = math.inf
        for contour in contours:
            image_object = ImageObject(contour, i)
            image_objects.append(image_object)
            minX = min(minX, image_object.min_x)
            maxX = max(maxX, image_object.max_x)
            minY = min(minY, image_object.min_y)
            maxY = max(maxY, image_object.max_y)
            i += 1
        print('i = ', i)
        return maxX, maxY, minX, minY
