#!/usr/bin/python
# -*- coding:utf-8 -*-

import logging
import logging.config
import arrow
from PIL import Image, ImageDraw, ImageFont, ImageOps


class Clock():

    def __init__(self, config):
        """Make a base Clock that handles all the abstract drawing.

        Keyword arguments:
        config -- a ConfigParser reference for configuration
        """
        from datetime import datetime
        self.logger = logging.getLogger('CLOCK')
        self.tzinfo = datetime.now().astimezone().tzinfo
        self.erase_offset = config.get('host', 'erase')
        self.width, self.height = map(
            int, config.get('host', 'size').split('x'))
        self.large_font = ImageFont.truetype(font=config.get(
            'font', 'large_font'), size=config.getint('font', 'large_size'))
        self.small_font = ImageFont.truetype(font=config.get(
            'font', 'small_font'), size=config.getint('font', 'small_size'))

    def make_canvas(self):
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
        import os
        import sys
        super().__init__(config)
        self.logger = logging.getLogger('EPD')
        libdir = config.get('lib', 'dir')
        if os.path.exists(libdir):
            self.logger.debug(f'Library exists! {libdir}')
            sys.path.append(libdir)
            import epd12in48b
        else:
            self.logger.critical(f'No library??? {libdir}')
            sys.exit(-100)

        self.epd = epd12in48b.EPD()
        self.epd.Init()
        self.width = epd12in48b.EPD_WIDTH
        self.height = epd12in48b.EPD_HEIGHT

        if clear:
            self.logger.info('Clearing display')
            self.epd.clear()
        super().make_canvas()

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
        self.epd.display(redimage, blackimage)
        self.logger.debug('Finished display, starting sleep')
        self.epd.EPD_Sleep()
        self.logger.debug('Finished sleep')


class PIL_Clock(Clock):
    def __init__(self, config):
        """Make an PIL-only Clock.

        Keyword arguments:
        config -- a ConfigParser reference for configuration
        """
        super().__init__(config)
        self.logger = logging.getLogger('PIL')
        super().make_canvas()

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
    import platform

    config = get_config()

    logging.config.fileConfig(config)
    logger = logging.getLogger('MAIN')
    logger.info('Starting!')

    target = config.get('host', 'target')
    if platform.node() == target:
        eink = EPD_Clock(config)
    else:
        logger.warning(
            f'Not e-ink on {target}, will use PIL simulation instead')
        eink = PIL_Clock(config)
    eink.draw_time()
    eink.display()
