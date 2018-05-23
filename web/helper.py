from config import basedir
from web import db, app
from web.models import User
from PIL import Image, ImageDraw, ImageEnhance
from web.models import User, AnonUser, RoomDeviceColorConnector
from web import app
from functools import wraps
from flask import session, redirect, url_for, render_template
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

def calibrate_resolution(resolution, w, h):
    width = resolution[0]
    height = resolution[1]
    print('!!!!!!!!!!!!!!!!!!1', width, height)
    if (width/height) > (w/h):
        while True:
            e = abs((width/height) - (w/h))
            height+=2
            if e < abs((width/height) - (w/h)):
                height-=2
                return [width, height]
    if (width/height) < (w/h):
        while True:
            e = abs((width/height) - (w/h))
            width+=2
            if e < abs((w/h) - (width/height)):
                width-=2
                return [width, height]
    return [width, height]
            
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
    new_resolution = calibrate_resolution(resolution, 16, 9)
    deltax = (new_resolution[0] - resolution[0]) / 2
    deltay = (new_resolution[1] - resolution[1]) / 2

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
        if rect[2] < -85 and rect[2] > -95:
            firsty = int(rect[0][1] - rect[1][0] / 2) + deltay
            lasty = int(rect[0][1] + rect[1][0] / 2) + deltay
            firstx = int(rect[0][0] - rect[1][1] / 2) + deltax
            lastx = int(rect[0][0] + rect[1][1] / 2) + deltax
        else:
            firsty = int(rect[0][1] - rect[1][1] / 2) + deltay
            lasty = int(rect[0][1] + rect[1][1] / 2) + deltay
            firstx = int(rect[0][0] - rect[1][0] / 2) + deltax
            lastx = int(rect[0][0] + rect[1][0] / 2) + deltax
        print('--------------------------------------------------')
        print(rect)
        print(color, user)
        print(resolution, new_resolution)
        print(minX,minY)
        print(firstx, firsty, ';', lastx, lasty)
        width = ( new_resolution[0] / (lastx - firstx) ) * 100

        left = - ( firstx / new_resolution[0] ) * width
        top = - ( firsty / new_resolution[1] ) * width

        print(top, left)
        #Записываем-с
        user.res_k = int(width)
        user.top = int(top)
        user.left = int(left)

        db.session.commit()
    
    del draw      
        
    room_map.save(os.path.join(basedir, 'images', room.token + '_map.jpg'))   


def image_loaded(request, room, user, users, null_form, image_form, Room_Form):
    token = room.token
    room_map_url = token + '_map'
    if 'image' not in request.files:
        return render_template('room.html', room=room, user=cur_user(),
                               color=user.color, users=users,
                               image_form=null_form,
                               Room_Form=Room_Form, loaded=False,
                               map_ex=os.path.exists(basedir + '/images/' + token + '_map.jpg'),
                               room_map=room_map_url, anon=user, count=len(users)+1)

    file = request.files['image']
    if file.filename == '':
        return render_template('room.html', room=room, user=cur_user(),
                               calibrate_url=calibrate_url, color=user.color, users=users,
                               image_form=null_form,
                               Room_Form=Room_Form, loaded=False, 
                               map_ex=os.path.exists(basedir + '/images/' + token + '_map.jpg'),
                               room_map=room_map_url, anon=user, count=len(users)+1)

    if file and allowed_image(file.filename):
        file.save(basedir + '/images/' + room.token + '.' + file.filename.split('.')[-1].lower())
        try:
            parse(room, users, basedir + '/images/' + room.token + '.jpg')
        except:
            return render_template('room.html', room=room, user=cur_user(), color=user.color, users=users,
                                       image_form=image_form, count=len(users),
                                       Room_Form=Room_Form, loaded=True, room_map=room_map_url, anon=user,
                                       msg="Мы не смогли идентифицировать устройства, попробуйте загрузить другую фотографию.",
                                       map_ex=os.path.exists(basedir + '/images/' + token + '_map.jpg'))
        return render_template('room.html', room=room, user=cur_user(), color=user.color, users=users,
                               image_form=image_form, anon=user,
                               Room_Form=Room_Form, loaded=True, room_map=room_map_url, count=len(users)+1,
                               map_ex=os.path.exists(basedir + '/images/' + token + '_map.jpg'))


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
