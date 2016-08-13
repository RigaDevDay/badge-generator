#!/usr/bin/python3
# -*- coding: utf-8 -*-

from wand.image import Image
from wand.sequence import Sequence
from wand.drawing import Drawing
from wand.color import Color
from qrcode.image.svg import SvgImage
import qrcode
import io
import csv
import logging
import sys
from unidecode import unidecode

# Requirements:
# pip install wand qrcode unidecode
# Download files `Titillium-Semibold.otf`, `Titillium-Regular.otf`, `Titillium-Italic.otf`
#    from https://www.fontsquirrel.com/fonts/Titillium
#
# Usage:
# create file data.csv in format `name, company, email, days, tag`
#   where tag in `staff, press, speaker, sponsor`
#   where days in `2,3,5` (5=2+3)
# python3 generate.py 1
#
# Docs:
# http://docs.wand-py.org/en/0.4.2/#user-s-guide
#
# Apps
# BadgerScan (with possibility to export all contacts to csv)
# http://www.badgerscan.org/
# https://itunes.apple.com/us/app/badgerscan/id902271396?mt=8
# https://play.google.com/store/apps/details?id=org.badgescan.contacts&hl=lv

# Settings

PAGE_DPI = 300
PAGE_WIDTH = 1240  # 2480 a4
PAGE_HEIGHT = 1748  # 3508 a4
MARGINS = 36  # (2480-1167*2)/2
BADGE_DPI = 296
BADGE_WIDTH = 1167  # 101mm @ 300dpi = 1192 but we need heigth to fit in 143mm :(
BADGE_HEIGHT = 1689  # 143mm @ 300dpi
filename = 'data.csv'
logging.root.setLevel(logging.DEBUG)

# Code
vcard = """BEGIN:VCARD
N:%s
ORG:%s
EMAIL:%s
END:VCARD
"""
badges = {
    '2': Image(filename='rdd2016-Badge-Yellow.svg', resolution=BADGE_DPI),
    '5': Image(filename='rdd2016-Badge-Blue.svg', resolution=BADGE_DPI),
    '3': Image(filename='rdd2016-Badge-Red.svg', resolution=BADGE_DPI)
}
colors = {
    'speaker': '#f55549',
    'sponsor': '#ffd500',
    'press': '#00a6eb',
    'staff': '#000',
}
badge_backside = Image(filename='rdd2016-Badge-Backside.svg', resolution=BADGE_DPI)

def draw_front(badge, name, company, tag):
    height_multiplier = 1.24

    if name != "":
        with Drawing() as draw:
            draw.font_size = 32
            draw.text_alignment = 'center'
            draw.font = 'Titillium-Semibold.otf'
            draw.fill_color = Color('#00487F')
            first_name, last_name = name.split(" ", 1)
            draw.text(int(badge.width / 2), int((badge.height / 2) * height_multiplier), first_name)
            height_multiplier += 0.15
            draw.text(int(badge.width / 2), int((badge.height / 2) * height_multiplier), last_name)
            height_multiplier += 0.12
            draw(badge)
    else:
        height_multiplier += 0.12 + 0.15

    if tag in colors:
        with Drawing() as draw:
            draw.width = badge.width
            draw.font_size = 18
            draw.text_alignment = 'center'
            draw.font = 'Titillium-Regular.otf'
            draw.fill_color = Color('#fff')
            draw.text_under_color = Color(colors.get(tag))
            draw.text(int(badge.width / 2), int((badge.height / 2) * height_multiplier), ' %s ' % tag)
            draw(badge)
            height_multiplier += 0.12

    if company != "":
        with Drawing() as draw:
            draw.font_size = 16
            draw.text_alignment = 'center'
            draw.font = 'Titillium-Italic.otf'
            draw.fill_color = Color('#00A6EB')
            draw.text(int(badge.width / 2), int((badge.height / 2) * height_multiplier), company)
            draw(badge)


def draw_back(badge, name, company, email):
    with io.BytesIO() as stream:
        qr_size = 400
        data = vcard % (name, company, email)
        qrz = qrcode.make(unidecode(data), image_factory=SvgImage, box_size=100)
        qrz.save(stream)
        stream.seek(0)

        qr = Image(file=stream)
        qr.sample(qr_size, qr_size)
        badge.composite(qr, left=int((badge.width - qr_size) / 2), top=int((badge.height / 2) * 1.40))

        if name!="":
            with Drawing() as draw:
                draw.font_size = 7

                draw.font = 'Titillium-Regular.otf'
                draw.text_alignment = 'center'
                draw.text(int(badge.width / 2), int((badge.height / 2) * 1.40 + qr_size), name)
                draw(badge)


class Canvas:
    def __init__(self):
        self.result = Image()
        self.pages = Sequence(self.result)
        self.result.sequence = self.pages
        self.badge_x = 0
        self.badge_y = 0
        self.page = self.new_page()

    def new_page(self):
        page = Image(width=PAGE_WIDTH, height=PAGE_HEIGHT, resolution=PAGE_DPI, background=Color('#fff'))
        # If more than one badge on page
        # with Drawing() as draw:
        #     draw.font_size = 20
        #     draw.text_alignment = 'center'
        #     draw.text(int(page.width / 2), 30, "Page %s" % (len(self.pages) + 1))
        #     draw(page)
        return page

    def add(self, badge, reverse=False):
        if badge.width != BADGE_WIDTH:
            logging.debug("scaling")
            badge.sample(BADGE_WIDTH, BADGE_HEIGHT)

        if reverse:
            self.page.composite(
                badge, left=PAGE_WIDTH - (MARGINS + self.badge_x) - BADGE_WIDTH, top=MARGINS + self.badge_y)
        else:
            self.page.composite(badge, left=MARGINS + self.badge_x, top=MARGINS + self.badge_y)

        self.badge_x += BADGE_WIDTH
        if self.badge_x + BADGE_WIDTH > PAGE_WIDTH - MARGINS:
            self.badge_x = 0
            self.badge_y += BADGE_HEIGHT
            if self.badge_y + BADGE_HEIGHT > PAGE_HEIGHT - MARGINS:
                self.badge_y = 0
                self.pages.append(self.page)
                self.page = self.new_page()

    def save(self, filename):
        # self.pages.append(self.page)
        self.result.save(filename=filename)


def main():
    front = Canvas()
    back = Canvas()

    with open(filename) as csvfile:
        for i, (name, company, email, days, tag) in enumerate(csv.reader(csvfile)):
            logging.debug('%s: %s' % (i, name))

            if days == '?':
                days = ['2', '3']

            for day in days:
                if badges.get(day) is not None:
                    badge_front = badges.get(day).clone()
                    draw_front(badge_front, name, company, tag)
                    front.add(badge_front)

                    badge_back = badge_backside.clone()
                    draw_back(badge_back, name, company, email)
                    back.add(badge_back, True)

    front.save('front %s.pdf' % sys.argv[1])
    back.save('back %s.pdf' % sys.argv[1])

if __name__ == '__main__':
    main()
