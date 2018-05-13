from config import basedir
from web import db, app
from web.models import User
from PIL import Image, ImageDraw, ImageEnhance
from web.models import User, AnonUser
from web import app
from functools import wraps
from flask import session, redirect, url_for
import numpy as np
import math
import cv2
import os


def allowed_image(filename):
    return ('.' in filename and
            filename.split('.')[-1].lower() in app.config["ALLOWED_IMAGE_EXTENSIONS"])


def allowed_file(filename):
    return ('.' in filename and
            filename.split('.')[-1].lower() in app.config["ALLOWED_EXTENSIONS"])


def requiresauth(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if cur_user() is None:
            return redirect(url_for('log'))
        return f(*args, **kwargs)

    return wrapped


def read_multi(pid):
    path = basedir + '/images/%s.jpg' % pid
    with open(path, "rb") as im:
        f = im.read()
        b = bytearray(f)
        return b


def read_image(pid):
    path = basedir + '/video/%s/preview.png' % pid
    with open(path, "rb") as im:
        f = im.read()
        b = bytearray(f)
        return b


def read_video(vid):
    path = basedir + '/video/%s/video.mp4' % vid
    with open(path, "rb") as im:
        f = im.read()
        b = bytearray(f)
        return b


def is_true_pixel(r, g, b, R, G, B):
    k=60
    return (r in range(R-k, R+k))and(g in range(G-k, G+k))and(b in range(B-k, B+k))


def parse(room, users, impath):
    img = cv2.imread(impath) # Читаем изображение
    hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV) # Меняем цветовую схему с BGR на HSV

    items = list()

    maxX = maxY = -math.inf
    minY = minX = math.inf
    
    for user in users:
        R = int(user.color[1:3], 16)
        G = int(user.color[3:5], 16)
        B = int(user.color[5:7], 16)
        color = (B,G,R)

        # Меняем схему цвета на HSV, достаём из него только Hue
        hsv_color = np.array(color, dtype=np.uint8, ndmin=3) 
        hue = cv2.cvtColor(hsv_color, cv2.COLOR_BGR2HSV).flatten()[0] 

        # Создаём минимальный предел
        h_min = np.array([max(hue - 10, 0), 100, 100], dtype=np.uint8) 
        # И максимальный
        h_max = np.array([min(hue + 10, 179), 255, 255], dtype=np.uint8) 

        # Накладываем цветовой фильтр
        thresh = cv2.inRange(hsv_img, h_min, h_max) 
        # Ищем контуры
        _, contours, hierarchy = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) 

        # Создаём прямоугольник из контура с наибольшей площадью
        rect = cv2.minAreaRect( sorted(contours, key = cv2.contourArea, reverse = True)[0] ) 

        # Переводим в вершины, округляя координаты
        box = np.int0(cv2.boxPoints(rect)) 
        minX = min(minX, np.ndarray.min( box[...,0] ))
        maxX = max(maxX, np.ndarray.max( box[...,0] ))
        minY = min(minY, np.ndarray.min( box[...,1] ))
        maxY = max(maxY, np.ndarray.max( box[...,1] ))

        items.append([ user, rect, (color[2], color[1], color[0]) ])
        
    # Находим разрешение
    resolution = (maxX - minX, maxY - minY)

    room_map = Image.new('RGB', resolution, (255, 255, 255))
    draw = ImageDraw.Draw(room_map)

    for item in items:
        #Преобразуем-с
        rect = item[1]
        item = (item[0], ( (rect[0][0] - minX, rect[0][1] - minY), rect[1], rect[2]), item[2])      

        user, rect, color= item

        #Рисуем-с
        draw.polygon(np.int0(cv2.boxPoints(rect)).flatten().tolist(), fill=color)
        
        #Считаем-с
        firsty = int(rect[0][1] - rect[1][1] / 2)        
        lasty = int(rect[0][1] + rect[1][1] / 2)
        firstx = int(rect[0][0] - rect[1][0] / 2)
        lastx = int(rect[0][0] + rect[1][0] / 2)
        print(firstx, firsty, ';', lastx, lasty)
        width = ( resolution[0] / (lastx - firstx) ) * 100
        height = ( resolution[1] / (lasty - firsty) ) * 100
        res_k = max(width, height)

        left = - ( firstx / resolution[0] )
        top = - ( firsty / resolution[1] )

        #Записываем-с
        user.res_k = int(res_k)
        user.top = int(top)
        user.left = int(left)

        db.session.commit()
    
    del draw      
        
    room_map.save(os.path.join(basedir, 'images', room.token + '_map.jpg'))   


def cur_user():
    if 'Login' in session:
        return User.get(login=session['Login'])
    return None


def anon_user():
    user = None
    if 'anon_id' in session:
        user = AnonUser.get(id=session['anon_id'])
    if not user:
        user = AnonUser()
        session['anon_id'] = user.id
    return user
