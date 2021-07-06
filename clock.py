#!/usr/bin/python
# -*- coding:utf-8 -*-

import logging
import logging.config
import os
import pickle
import sys
from datetime import datetime

import arrow
from PIL import Image, ImageDraw, ImageFont

try:
    import epd12in48b
except ModuleNotFoundError:
    # not on an e-ink system; later factory check will load the right class
    pass


class RunningAverage():
    """Track the running average of a value

    Credit to Dima Lituiev for https://stackoverflow.com/a/62768606
    """

    def __init__(self):
        self.average = 0
        self.n = 0

    def __call__(self, new_value):
        self.n += 1
        self.average = (self.average * (self.n-1) + new_value) / self.n

    def __float__(self):
        return self.average

    def __repr__(self):
        return "average: " + str(self.average)


class Clock():

    def __init__(self, config, size=None):
        """Make a base Clock that handles all the abstract drawing.

        Keyword arguments:
        config -- a ConfigParser reference for configuration
        size -- a two-tuple of width, height (default None)
        """

        self.logger = logging.getLogger('eink_clock')

        # get local timezone information
        self.tzinfo = datetime.now().astimezone().tzinfo

        self.erase_offset = config.get('host', 'erase')

        # if the default was passed in, get the size from the config file
        if size is None:
            self.width, self.height = map(
                int, config.get('host', 'size').split('x'))
        # otherwise, unpack the tuple
        else:
            self.width, self.height = size

        self.large_font = ImageFont.truetype(font=config.get(
            'font', 'large_font'), size=config.getint('font', 'large_size'))
        self.small_font = ImageFont.truetype(font=config.get(
            'font', 'small_font'), size=config.getint('font', 'small_size'))

        self.canvas = Image.new('RGB', (self.width, self.height), 'WHITE')
        self.draw = ImageDraw.Draw(self.canvas)

    def draw_time(self):
        """Generate the time display."""

        time = arrow.now(self.tzinfo)

        self.logger.debug('drawing...')

        # draw the day name in top dead center
        day = time.format('dddd')
        _, h = self.draw.textsize(day, font=self.large_font)
        self.draw.text((self.width/2, 0), day, font=self.large_font,
                       fill='RED', anchor='ma')

        # draw the date to the right and below
        self.draw.text((self.width, h), time.format('MMMM Do, YYYY'), font=self.small_font,
                       fill='BLUE', anchor='ra')

        # draw the time to the left and below
        #  with the first digit highlighted in read and the rest in black
        hour_tens = f'{time.hour // 10}'
        time_rem = f'{time.hour % 10}:{time.minute:02d}'
        w, _ = self.draw.textsize(hour_tens, font=self.large_font)
        self.draw.text((0, h), hour_tens,
                       font=self.large_font, fill='RED', anchor='la')
        self.draw.text((w, h), time_rem,
                       font=self.large_font, fill='BLUE', anchor='la')

        # draw a reminder to erase the display at the specified offset
        erase_date = time.dehumanize(self.erase_offset)
        erase_info = f'{time.format("YYYY-MM-DD")} erase by {erase_date.format("YYYY-MM-DD")}'
        self.draw.text((self.width/2, self.height),
                       erase_info, font=self.small_font, fill='BLUE', anchor='md')

    def display(self):
        """Display the canvas to user."""
        pass


class EPD_Clock(Clock):
    def __init__(self, config, clear=False):
        """Make an EPD-aware Clock.

        Keyword arguments:
        config -- a ConfigParser reference for configuration
        clear -- a boolean indicating whether to clear the EPD first (default False)
        """

        self.logger = logging.getLogger('eink_clock')

        self.epd = epd12in48b.EPD()
        self.epd.Init()
        if clear:
            self.logger.info('Clearing display')
            self.epd.clear()

        try:
            self.update_avg = pickle.load(open('update.pkl', 'rb'))
        except FileNotFoundError:
            self.update_avg = RunningAverage()

        super().__init__(config, (epd12in48b.EPD_WIDTH, epd12in48b.EPD_HEIGHT))

    def display(self):
        """Send the canvas to the display and then sleep."""
        super().display()

        # use the RED channel as the red image
        #  but convert it to 1-bit as the display draws "black" on white
        #  and rotate it to match display orientation
        redimage = self.canvas.getchannel(
            channel='R').convert(mode='1', dither=Image.NONE).rotate(180)

        # use the BLUE channel as the black image
        #  but convert it to 1-bit as the display draws "black" on white
        #  and rotate it to match display orientation
        blackimage = self.canvas.getchannel(
            channel='B').convert(mode='1', dither=Image.NONE).rotate(180)
        self.logger.debug('Starting display')
        start = arrow.now(self.tzinfo)
        self.epd.display(redimage, blackimage)
        elapsed = (arrow.now(self.tzinfo) - start)
        self.update_avg(elapsed)
        self.logger.debug(
            f'Finished display in {elapsed:.3f}s (average {self.update_avg:.3f}s), starting sleep')
        self.epd.EPD_Sleep()
        self.logger.debug('Finished sleep')
        pickle.dump(self.update_avg, open('update.pkl', 'wb'))


class PIL_Clock(Clock):
    def __init__(self, config):
        """Make an PIL-only Clock.

        Keyword arguments:
        config -- a ConfigParser reference for configuration
        """
        super().__init__(config)

    def display(self):
        """Show the canvas to the user."""
        super().display()
        self.canvas.show()

        # also demonstrate the EPD images:
        # use the RED channel as the red image
        #  but convert it to 1-bit as the display draws "black" on white
        #  and rotate it to match display orientation
        redimage = self.canvas.getchannel(
            channel='R').convert(mode='1', dither=Image.NONE).rotate(180)
        redimage.show()

        # use the BLUE channel as the black image
        #  but convert it to 1-bit as the display draws "black" on white
        #  and rotate it to match display orientation
        blackimage = self.canvas.getchannel(
            channel='B').convert(mode='1', dither=Image.NONE).rotate(180)
        blackimage.show()


def get_config():
    import configparser
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config


if __name__ == '__main__':
    config = get_config()

    logging.config.fileConfig(config)
    logger = logging.getLogger('eink_clock')
    logger.info('Starting!')

    if 'epd12in48b' in sys.modules:
        eink = EPD_Clock(config)
    else:
        logger.warning(
            f'Not e-ink, will use PIL simulation instead')
        eink = PIL_Clock(config)
    eink.draw_time()
    eink.display()
