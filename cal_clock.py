#!/usr/bin/python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: FAFOL

import logging
import logging.config
import os
import pickle
import sys
from datetime import datetime

import arrow
from PIL import Image, ImageDraw, ImageFont

import clock

if __name__ == '__main__':
    config = clock.get_config()

    logging.config.fileConfig(config)
    logger = logging.getLogger('eink_calendar')
    logger.info('Starting!')

    if 'epd12in48b' in sys.modules:
        eink = clock.EPD_Clock(config)
    else:
        logger.warning(
            f'Not e-ink, will use PIL simulation instead')
        eink = clock.PIL_Clock(config)
    eink.draw_calendar()
    eink.display()
