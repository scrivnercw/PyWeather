#!/usr/bin/env python
#
#  PyWeather example script for reading Davis Vantage Pro(2) data and uploading
#  to the WeatherUnderground.com Personal Weather Station (PWS) site.
#
#  Author:  Patrick C. McGinty
#  Email:   pyweather@tuxcoder.com
#  Date:    Sunday, May 02 2010
#
"""
Periodically read data from a local weather station and upload to the
Weather Underground PWS site.
"""

import os
import sys
import time
import logging
import optparse

import weather.stations
import weather.services

log = logging.getLogger('')

ARCHIVE_PER       = 10  # intervals (in minutes) between each archive record
GUST_UPDATE_PER   = 10  # minutes to report last gust reading
GUST_MPH_MIN      = 7   # minimum mph of gust above avg wind speed to report


class NoSensorException(Exception): pass


class WindGust(object):
   NO_VALUE = ('NA','NA')

   def __init__(self):
      self.value = self.NO_VALUE
      self.count = 0

   def get( self, station, delay ):
      '''
      return gust data, if above threshold value and current time is inside
      reporting window period
      '''
      rec = station.fields['Archive']
      # process new data
      if rec:
         threshold = station.fields['WindSpeed10Min'] + GUST_MPH_MIN
         if rec['WindHi'] >= threshold:
            self.value = (rec['WindHi'],rec['WindHiDir'])
            self.count = GUST_UPDATE_PER * 60 / delay
         else:
            self.value = self.NO_VALUE

      # return gust value, if remaining time is left, and valid
      if self.count:
         self.count -= 1
      else:
         self.value = self.NO_VALUE

      log.debug('wind gust of {0} mph from {1}'.format(*self.value))
      return self.value
WindGust = WindGust()


def weather_update(station,net,pwsid,password):
   '''
   main execution loop. query weather data and post to online service.
   '''
   station.parse()      # read weather data

   # santity check weather data
   if station.fields['TempOut'] > 200:
      raise NoSensorException(
            'Out of range temperature value: %.1f, check sensors' %
            (station.fields['TempOut'],))

   gust, gust_dir = WindGust.get( station )

   # upload data in the following order:
   net.set(
         pressure    = station.fields['Pressure'],
         dewpoint    = station.fields['DewPoint'],
         humidity    = station.fields['HumOut'],
         tempf       = station.fields['TempOut'],
         rainin      = station.fields['RainRate'],
         rainday     = station.fields['RainDay'],
         dateutc     = station.fields['DateStampUtc'],
         windspeed   = station.fields['WindSpeed10Min'],
         winddir     = station.fields['WindDir'],
         windgust    = gust,
         windgustdir = gust_dir, )

   # send to WeatherUnderground
   net.publish( pwsid, password )


def init_log( quiet, debug ):
   '''
   setup system logging to desired verbosity.
   '''
   from logging.handlers import SysLogHandler
   fmt = logging.Formatter(
         "vpro-to-wu.%(name)s %(levelname)s - %(message)s")
   facility = SysLogHandler.LOG_DAEMON
   syslog = SysLogHandler(address='/dev/log',facility=facility)
   syslog.setFormatter( fmt )
   log.addHandler(syslog)
   if not quiet:
      console = logging.StreamHandler()
      console.setFormatter( fmt )
      log.addHandler(console)
      log.setLevel(logging.INFO)
      if debug:
         log.setLevel(logging.DEBUG)


def get_options(parser):
   '''
   read command line options to configure program behavior.
   '''
   parser.add_option('-d', '--debug', dest='debug', action="store_true",
         default=False, help='enable verbose debug logging')
   parser.add_option('-q', '--quiet', dest='quiet', action="store_true",
         default=False, help='disable all console logging')
   parser.add_option('-t', '--tty', dest='tty', default='/dev/ttyS0',
         help='set serial port device [/dev/ttyS0]')
   parser.add_option('-u', '--update-delay', dest='delay', default=60,
         help='polling/update delay in seconds [60]')
   return parser.parse_args()


if __name__ == '__main__':
   prog = os.path.basename(sys.argv[0])
   parser = optparse.OptionParser(usage=prog+" USER PASSWORD [options]")
   opts,args = get_options(parser)
   init_log( opts.quiet, opts.debug )

   if len(args) != 2:
      log.error('invalid id/password parameters')
      parser.print_help()
      sys.exit(-1)
   pwsid,password = args

   station = weather.stations.VantagePro(opts.tty, ARCHIVE_PER)
   net = weather.services.Publisher()

   while True:
      # delay till next update time
      next_update = opts.delay - (time.time() % opts.delay)
      log.info('sleep')
      time.sleep( next_update )

      try:
         weather_update( station, net, pwsid, password)
      except (Exception) as e:
         log.error(e)

