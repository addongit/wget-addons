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

def download(url, override_filename=None):
  local_name = url2name(url)
  req = urllib2.Request(url)
  r = urllib2.urlopen(req)
  
  if r.info().has_key('Content-Disposition'):
    # If the response has Content-Disposition, we take file name from it
    local_name = r.info()['Content-Disposition'].split('filename=')[1]
    if local_name[0] == '"' or local_name[0] == "'": local_name = local_name[1:-1]
  elif r.url != url: 
    # if we were redirected, the real file name we take from the final URL
    local_name = url2name(r.url)

  filename_on_disk = override_filename if not override_filename is None else local_name
  
  f = open(filename_on_disk, 'wb')
  f.write(r.read())
  f.close()
  return filename_on_disk


def unzip(path, archive=False):
  if not os.path.exists(path): raise Exception('%s does not exist.' % path)
  os.chdir(path)
  
  processed_files = { 'archived':   [],
                      'extracted':  []
                    }

  for f in glob.glob('*.zip'):
    with ZipFile(f, 'r') as z:
      z.extractall()
  #if archive: processed_files['archived'] = archive_zips(path)
  clean_up_zips(path)
  for d in os.listdir(path):
    if d == '_archived': continue
    processed_files['extracted'].append(os.path.join(path, d))
  return processed_files

def archive_zips(path):
  archive_path = os.path.join(path, '_archive')
  if not os.path.exists(path): raise Exception('%s does not exist.' % path)
  os.chdir(path)
  archived_files = []
  if not os.path.exists(archive_path): os.makedirs(archive_path)
  for f in glob.glob('*.zip'):
    archive_file_src_path = os.path.join(path, f)
    archive_file_dst_path = os.path.join(archive_path, f)
    if os.path.exists(archive_file_dst_path): os.remove(archive_file_dst_path)
    shutil.move( archive_file_src_path, archive_file_dst_path )
    archived_files.append(archive_file_dst_path)
  return archived_files


def clean_up_zips(path):
  if not os.path.exists(path): raise Exception('%s does not exist.')
  cwd = os.getcwd()
  os.chdir(path)
  for f in glob.glob('*.zip'): 
    zip_path = os.path.join(path, f)
    os.remove(zip_path)
  os.chdir(cwd)
  

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
  if not os.path.exists(profile): raise Exception('%s does not exist motherbitches' % profile)
  addons = []
  for a in open(profile).readlines():
    if ';' in a or a is None or len(a) == 0 or a == '\n': continue
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
                   'merge_common':    opts['common'],
                   'reset_master':    opts['reset_master']
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
  if verbose: print 'Using the following profiles:\n\t%s' % '\n'.join(addons_profiles)

  cwd = os.getcwd()
  os.chdir( app_settings['depot_folder'] )
  
  master_path = os.path.join(app_settings['depot_folder'], 'master')
  #master_archive_path = os.path.join(master_path, '_archive')

  #if not os.path.exists(master_path): os.makedirs(master_path)
  #if not os.path.exists(master_archive_path): os.makedirs(master_archive_path)

  for profile in addons_profiles:
    profile_name = profile.split('.')[0]
    full_depot_profile = os.path.join( app_settings['depot_folder'], profile_name )
    
    if os.path.exists(full_depot_profile):
      if verbose: print '(%s) Cleaning current addon collection.' % profile_name
      shutil.rmtree(full_depot_profile)

    if not os.path.exists( full_depot_profile ): 
      if verbose: print '(%s)\tCreating %s' % (profile_name, full_depot_profile)
      
      if dry_run:
        pass
      else:
        os.makedirs( full_depot_profile )
    
    os.chdir(full_depot_profile)
    
    profile_full_path = os.path.join(app_settings['profiles_folder'], profile)
    
    if verbose: print '(%s)\tprofile_full_path: %s' % (profile_name, profile_full_path)
    
    for addon_url in get_addons_list( profile_full_path ):
      if verbose: print '(%s)\tDownloading %s' % (profile_name, addon_url)
      if dry_run: 
        pass
      else:
        addon_name = download(addon_url)

      if app_settings['extract']: 
        if verbose: 
            print '(%s)\tUnzipping %s' % (profile_name, addon_name)
            #print '(%s)\tArchive:\t%s' % ( profile_name, app_settings['archive'] )
        if dry_run:
          pass 
        else:
          files = unzip( full_depot_profile, app_settings['archive'] )


    # Master cloning
    #============================================================================
    #archive_profile_path = os.path.join(full_depot_profile, '_archive')
    #if verbose: print '(%s) archive_profile_path: %s' % (profile_name, archive_profile_path)
    
    if app_settings['reset_master'] and profile_name == 'common':
      if verbose: print 'Resetting Master'
      shutil.rmtree(master_path)

    if not os.path.exists(master_path): os.makedirs(master_path)

    for f in os.listdir(full_depot_profile):
      if f == '_archive': continue
      if verbose: print '(%s) Merging %s into Master' % (profile_name, f)
      addon_src_path = os.path.join(full_depot_profile, f)
      addon_dst_path = os.path.join(master_path, f)

      if os.path.exists(addon_dst_path): shutil.rmtree(addon_dst_path)

      shutil.copytree(addon_src_path, addon_dst_path)
      
      #if os.path.exists(archive_profile_path):
      #  cwd = os.getcwd()
      #  os.chdir(archive_profile_path)
      #  for f in glob.glob('*.zip'):
      #    zip_dst = os.path.join(master_archive_path, f)
      #    zip_src = os.path.join(archive_profile_path, f)
      #    if verbose: print '(Master) Cloning %s into _archive/' % (f)
      #    if os.path.exists(zip_dst): os.remove(zip_dst)
      #    shutil.copy( zip_src, zip_dst )
      #  os.chdir(cwd)

    if verbose: 
      print '\n(%s) Addon listing after update:\n' % profile_name
      for a in os.listdir('./'):
        print '\t%s\n' % a
      print '\n'

  common_addons_path = os.path.join(app_settings['depot_folder'], 'common')
  common_addons_list = os.listdir(common_addons_path)

  if len(common_addons_list) == 1 and '_archive' in common_addons_list or len(common_addons_list) == 0: app_settings['merge_common'] = False

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

  os.chdir( cwd )

if __name__ == '__main__':

  def getOpts():
    '''
    Setup our cmdline variables.
    '''
    _parser = OptionParser(usage = "usage: %prog [options]")

    _parser.add_option( '--profile',
                        '-p',
                        '-b',
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
    
    _parser.add_option('--reset-master',
                        action='store_true',
                        default=False,
                        dest='reset_master',
                        help='Reset Master addon collection.')
    
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
             'common':          _opts.common, 
             'reset_master':    _opts.reset_master 
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
