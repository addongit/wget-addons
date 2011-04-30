#!/usr/bin/python

import ConfigParser
import sys
import glob
import os
import shutil
from optparse import OptionParser
import urllib2

from os.path import basename
from urlparse import urlsplit
from zipfile import ZipFile

def url2name(url):
  return basename(urlsplit(url)[2])

def download(url, localFileName = None):
  localName = url2name(url)
  req = urllib2.Request(url)
  r = urllib2.urlopen(req)
  if r.info().has_key('Content-Disposition'):
    # If the response has Content-Disposition, we take file name from it
    localName = r.info()['Content-Disposition'].split('filename=')[1]
    if localName[0] == '"' or localName[0] == "'":
      localName = localName[1:-1]
  elif r.url != url: 
    # if we were redirected, the real file name we take from the final URL
    localName = url2name(r.url)
  if localFileName: 
    # we can force to save the file as specified name
    localName = localFileName
  f = open(localName, 'wb')
  f.write(r.read())
  f.close()

def unzip(path, archive=False):
  if not os.path.exists(path): raise Exception('%s does not exist.' % path)
  os.chdir(path)
  for f in glob.glob('*.zip'):
    with ZipFile(f, 'r') as z:
      z.extractall()
  if archive: archive_zips(path)

def archive_zips(path):
  archive_path = os.path.join(path, '_archive')
  if not os.path.exists(path): raise Exception('%s does not exist.' % path)
  os.chdir(path)
  if not os.path.exists(archive_path): os.makedirs(archive_path)
  for f in glob.glob('*.zip'):
    print 'Archiving: %s' % f
    shutil.move( os.path.join(path, f), os.path.join(archive_path, f) )


def initConfig(config):
  ''' Initialize the config object pointed to $config's path.'''
  c = ConfigParser.ConfigParser()
  c.optionxform = str
  c.cwd = sys.path[0]
  c.cfg_path = os.path.join(c.cwd, config)
  return c


def find_all_profiles(profiles_path, profile=None):
  if not os.path.exists(profiles_path): raise Exception('%s does not exist' % profiles_path)
  cwd = os.getcwd()
  os.chdir(profiles_path)
  if not profile:
    contents = sorted( glob.glob('*.profile') )
  else:
    contents = glob.glob( '%s.profile' % profile )
  os.chdir(cwd)
  return contents or []


def get_addons_list(profile):
  print sys.path[0]
  if not os.path.exists(profile): raise Exception('%s does not exist motherbitches' % profile)
  addons = []
  for a in open(profile).readlines():
    if ';' in a or a is None or len(a) == 0 or a == '\n': continue
    print 'line: %s' % a
    addons.append(a.strip())
  return addons


def Main(opts):
  # Make sure config exists
  assert os.path.exists( opts['config'] )
  config = initConfig( opts['config'] )
  config.read(config.cfg_path)
   
  app_settings = { 'profiles':        opts['profiles'] if len(opts['profiles']) > 0 else ['common'],
                   'config':          opts['config'],
                   'verbose':         opts['verbose'],
                   'dry_run':         opts['dry_run'],
                   'profiles_folder': opts['profiles_folder'] if opts['profiles_folder'] else os.path.join( sys.path[0], config.get('local', 'profilesDirectory') ),
                   'depot_folder':    opts['depot_folder'] if opts['depot_folder'] else config.get('local', 'depotDirectory'),
                   'extract':         opts['extract'],
                   'archive':         opts['archive'],
                   'merge_common':    opts['common']
                 }

  verbose = app_settings['verbose']
  dry_run = app_settings['dry_run']

  if verbose: print 'VERBOSE Mode Enabled.'
  if dry_run: print '<<< DRY RUN >>> '

  # Use what was passed in for branch name
  # If 'all', determine which branches are present and use them instead.
  addons_profiles = []
  if 'all' in app_settings['profiles']:
    addons_profiles = find_all_profiles( app_settings['profiles_folder'] )
  else:
    for p in app_settings['profiles']:
      glob_profile = find_all_profiles( app_settings['profiles_folder'], p )
      if len(glob_profile) == 0: continue
      addons_profiles.append(glob_profile[0]) 
  print addons_profiles

  cwd = os.getcwd()
  os.chdir( app_settings['depot_folder'] )
  
  master_path = os.path.join(app_settings['depot_folder'], 'master')

  if not os.path.exists(master_path): os.makedirs(master_path)

  for profile in addons_profiles:
    full_depot_profile = os.path.join( app_settings['depot_folder'], profile.split('.')[0] )
    
    if not os.path.exists( full_depot_profile ): 
      if dry_run:
        print 'mkdir %s' % full_depot_profile
      else:
        os.makedirs( full_depot_profile )
    
    os.chdir(full_depot_profile)
    
    profile_full_path = os.path.join(app_settings['profiles_folder'], profile)
    
    for a in get_addons_list( profile_full_path ):
      if dry_run: 
        print 'download %s' % a
      else:
        download(a)
        # hacking master in
        os.chdir(master_path)
        download(a)
        os.chdir(full_depot_profile)

      if app_settings['extract']: 
        if dry_run:
          print 'unzip %s\narchive=%s' % ( full_depot_profile, app_settings['archive'] )
        else:
          unzip( full_depot_profile, app_settings['archive'] )
          os.chdir(master_path)
          unzip( master_path, app_settings['archive'] )
          os.chdir(full_depot_profile)

  common_addons_path = os.path.join(app_settings['depot_folder'], 'common')
  common_addons_list = os.listdir(common_addons_path)

  print '--common: %s' % app_settings['merge_common']
  if len(common_addons_list) == 1 and '_archive' in common_addons_list or len(common_addons_list) == 0: app_settings['merge_common'] = False
  print '--common: %s' % app_settings['merge_common']

  if app_settings['merge_common']:
    for profile in addons_profiles:
      # if common, we have nothing to merge ;)
      if 'common' in profile: continue
      print 'Merging common to profile: %s' % profile
      
      for addon in common_addons_list:
        # if its the _archive directory or a single file of any type, skip it
        addon_src_path = os.path.join(common_addons_path, addon)

        if '_archive' == addon or not os.path.isdir(addon_src_path): continue
        
        full_depot_profile = os.path.join( app_settings['depot_folder'], profile.split('.')[0] )
        addon_dst_path = os.path.join(full_depot_profile, addon)

        if dry_run:
          print 'copying %s to %s' % (addon_src_path, addon_dst_path)
        else:
          shutil.copytree(addon_src_path, addon_dst_path)


  print os.listdir('./')

  os.chdir( cwd )

if __name__ == '__main__':

  def getOpts():
    '''
    Setup our cmdline variables.
    '''
    _parser = OptionParser(usage = "usage: %prog [options]")

    _parser.add_option( '--profile',
                        '-p',
                        action='append',
                        type='string',
                        default=[],
                        dest='profiles',
                        help="Profiles")

    _parser.add_option('--verbose',
                        '-v',
                        action='store_true',
                        default=False,
                        dest='verbose',
                        help='Verbose.')

    _parser.add_option('--dry-run',
                        action='store_true',
                        default=False,
                        dest='dry_run',
                        help='Dry Run.')

    _parser.add_option('--extract',
                        '-x',
                        action='store_true',
                        default=False,
                        dest='extract',
                        help='Extract.')
    
    _parser.add_option('--archive',
                        '-a',
                        action='store_true',
                        default=False,
                        dest='archive',
                        help='Archive.')
    
    _parser.add_option('--common',
                        action='store_true',
                        default=False,
                        dest='common',
                        help='Merge common addons with profiles.')
    
    _parser.add_option('--addons-depot-folder',
                       action='store',
                       type='string',
                       default=None,
                       dest='depot_directory',
                       help='Path to the addons depot folder.')

    _parser.add_option('--profiles-folder',
                       action='store',
                       type='string',
                       default=None,
                       dest='profiles_directory',
                       help='Path to the profiles directory.')

    _parser.add_option('--config',
                       action='store',
                       type='string',
                       default='./wget-addons.cfg',
                       dest='config',
                       help='Config file.')

    (_opts, _args) = _parser.parse_args()

    opts = { 'profiles':        _opts.profiles,
             'verbose':         _opts.verbose,
             'depot_folder':    _opts.depot_directory,
             'profiles_folder': _opts.profiles_directory,
             'config':          _opts.config,
             'dry_run':         _opts.dry_run, 
             'extract':         _opts.extract,
             'archive':         _opts.archive, 
             'common':          _opts.common 
           }

    return opts

  opts = getOpts()

  try:
    Main(opts)
  except KeyboardInterrupt, e:
    print >> sys.stderr, '\n\nExiting.'
  except Exception, e:
    print str('ERROR: %s' % e)
  sys.exit('Finished.\n')
