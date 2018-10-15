#!/usr/bin/python
# Lifx Stream Deck Controller
# by d-rez aka dark_skeleton

import pifx
from StreamDeck import StreamDeck
from PIL import Image, ImageFont, ImageDraw, ImageOps
from image_utils import ImageText
import colorsys
import rgb_to_kelvin
import threading
import random
import math
import subprocess
from time import sleep

# ---- USER CONFIG
# LifX API token saved in another file (see docs)
from creds import token 
deckexepath = "C:\Program Files\Elgato\StreamDeck"
chosenview = "scenes" # change this to "lights" if you want
exitafterchoice = False # change to False if you don't want the script to exit after you select a scene
# ---- END OF USER CONFIG

def generate_layout(deck, entries, page = 0):
    # Entries can be either lights or scenes
    global multiple_pages
    mapping = {}
    key = 0
    
    for entry in entries:
        mapping[key] = entry
        if (len(entries) < deck.key_count() and key < deck.key_count()) or \
           (len(entries) >= deck.key_count() and key >= page * (deck.key_count() - 3) and key < page * (deck.key_count() - 3) + deck.key_count() - 3):
            if chosenview == "scenes":
                deck.set_key_image(key - page * (deck.key_count() - 3), generate_icon(deck, entry['name'], color=(generate_gradient_colors(scene=entry))))
            elif chosenview == "lights":
                deck.set_key_image(key - page * (deck.key_count() - 3), generate_icon(deck, entry['label'], color=(generate_gradient_colors(light=entry))))
        key = key + 1        
    
    deck.set_key_image(deck.key_count() - 1, generate_icon(deck, "Exit", color=(255,255,255)))
    if len(entries) >= deck.key_count():
        multiple_pages = True
        deck.set_key_image(deck.key_count() - 2, generate_icon(deck, "<", color=(255,255,255)))
        deck.set_key_image(deck.key_count() - 3, generate_icon(deck, ">", color=(255,255,255)))
    
    deck.set_key_callback(key_callback)
    return mapping
    
def generate_gradient_colors(scene=None, light=None):
    if scene:
        #print(scene)
        h = scene['states'][0]['color']['hue']/360.0
        v = scene['states'][0]['brightness']
        s = scene['states'][0]['color']['saturation']
        k = scene['states'][0]['color']['kelvin']
        powered = 'on' in list(map(lambda x: x['power'], scene['states']))
    elif light:
        #print(light)
        powered = light['power'] == 'on'
        v = light['brightness']
        h = light['color']['hue']/360.0
        s = light['color']['saturation']
        k = light['color']['kelvin']
    else:
        return 0,0,0
    if not powered:
        b,g,r = (64,64,64)
    elif s == 0:
        b, g, r = rgb_to_kelvin.convert_K_to_RGB(k)
    else:
        b, g, r = colorsys.hsv_to_rgb(h,s,v)
        r = r * 255
        g = g * 255
        b = b * 255
        
    return int(r), int(g), int(b)
        
def generate_icon(deck, text, color=None):
    key_image_format = deck.key_image_format()
    width, height = (key_image_format['width'], key_image_format['height'])
    depth = key_image_format['depth']
    
    font = "verdana.ttf"
    fgcolor = (255,255,255)
    bgcolor = (0, 0, 0, 255)
    # We're upscaling the image here, hence 2*
    icon = Image.new("RGBA", (width*2,height*2), color=bgcolor)
    if color:
        r,g,b = (color)
        innerColor = [r,g,b]
        outerColor = [0, 0, 0] #Color at the corners 
        gradient = Image.new('RGBA', icon.size, color=0)
        for y in range(icon.height):
            for x in range(icon.width):

                #Find the distance to the center
                distanceToCenter = math.sqrt((x - icon.width/2) ** 2 + (y - icon.height/2) ** 2)

                #Make it on a scale from 0 to 1
                distanceToCenter = float(distanceToCenter) / (math.sqrt(2) * icon.width/2)

                #Calculate r, g, and b values
                r = outerColor[0] * distanceToCenter + innerColor[0] * (1 - distanceToCenter)
                g = outerColor[1] * distanceToCenter + innerColor[1] * (1 - distanceToCenter)
                b = outerColor[2] * distanceToCenter + innerColor[2] * (1 - distanceToCenter)


                #Place the pixel        
                gradient.putpixel((x, y), (int(r), int(g), int(b)))
        
        icon = gradient
        
    txtIm = ImageText(icon.size)
    txtIm.write_text_box((0,0), text, box_width=width*2, font_filename=font, font_size=26, color=bgcolor, place='center')
    txtImEx = txtIm.export()
    
    bb = ImageOps.mirror(Image.alpha_composite(icon,txtImEx).convert("RGB"))
    # We upscaled before and now we downscale the image - looks much nicer like that, with antialiasing
    bb.thumbnail((width,height), Image.ANTIALIAS)
    return bb.tobytes()
    
def key_callback(deck, key, state):
    global lights, currentpage, scenes
    skipaction=False
    if state:
        if key == d.key_count() - 1:
            deck.reset()
            deck.close()
            return
        if multiple_pages:
            if key == d.key_count() - 2:
                print("Previous page...")
                currentpage -= 1
                if currentpage < 0:
                    currentpage = 0
                skipaction=True
            elif key == d.key_count() - 3:
                print("Next page...")
                currentpage += 1
                skipaction=True
        if not skipaction:
            try:
                key = currentpage * (deck.key_count() - 3) + key
                if chosenview == "scenes":
                    print("Activating %s" % mapping[deck.id()][key]['name'])
                    p.activate_scene(mapping[deck.id()][key]['uuid'])
                    #deck.set_key_image(key, generate_icon(deck, mapping[deck.id()][key]['name']))
                elif chosenview == "lights":
                    print("Toggling %s" % mapping[deck.id()][key]['label'])
                    p.toggle_power("label:%s" % mapping[deck.id()][key]['label'])
                    #deck.set_key_image(key, generate_icon(deck, mapping[deck.id()][key]['name']))
                    if not exitafterchoice:
                        sleep(1)
                        # refresh light states
                        lights = p.list_lights()
                        generate_layout(d,lights, page = currentpage)
            except KeyError:
                print("Nothing to do...")
                return True
        
        if skipaction:
            # run only if we changed pages
            deck.reset()
            if chosenview == "scenes":
                generate_layout(deck, scenes, page = currentpage)
            elif chosenview == "lights":
                generate_layout(deck, lights, page = currentpage)
            
        if exitafterchoice:
            deck.reset()
            deck.close()
        
if __name__ == "__main__":
    print("Getting list of scenes and lights from Lifx Cloud...")
    currentpage = 0
    multiple_pages = False
    p = pifx.PIFX(api_key=token)
    scenes = p.list_scenes()
    lights = p.list_lights()
    print("Found %d scenes and %d controllable lights" % (len(scenes), len(lights)))

    print("Initializing Decks")
    manager = StreamDeck.DeviceManager()
    decks = manager.enumerate()
    print("Found {} Stream Decks.".format(len(decks)), flush=True)

    mapping = {}
    
    print("Killing Stream Deck software to prevent silly conflicts")
    subprocess.Popen(["taskkill", "/f", "/im", "StreamDeck.exe"])
    
    for d in decks:
        d.open()
        d.reset()

        if chosenview == "scenes":
            mapping[d.id()] = generate_layout(d,scenes)
        elif chosenview == "lights":
            mapping[d.id()] = generate_layout(d,lights)
        current_key_states = d.key_states()
        
        for t in threading.enumerate():
            if t is threading.currentThread():
                continue
            t.join()
        
    print("Starting StreamDeck software back up...")
    subprocess.Popen([deckexepath + "\StreamDeck.exe", "--runinbk"], shell=True,
             stdin=None, stdout=None, stderr=None, close_fds=True)
             