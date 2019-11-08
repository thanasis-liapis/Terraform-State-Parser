#!/usr/bin/env python3
#
# Script for parsing terraform state information and
# generating a dynamic ansible inventory file using
# terraform show command
#
# Date: 20191106
# Version: v5.0
#
# - This version supports infrastructure that is created 
#   1. using only root module resources.
#   2. using only child module resources.
#   3. using both root and child module resiources.
#
# - In case of creating an infrastructure with no floating ips, the ip that will be used for remote connection
#   is the ip of the network interface that will be defined in the cmd. If no NIC index is given, NIC 0 is used.
#
# - Requires terraform v0.12.x. Supports only terraform state files of version 4.
#
import json
import yaml
import subprocess
import os
import getopt
import sys
import urllib.request,urllib.parse
from urllib.error import HTTPError,URLError,ContentTooShortError
from socket import gethostbyname,gaierror

urlelement = []
tfresourceslist = []
allcomputeresourcesattr = []
allfloatingresourcesattr = []
iptype = 'floating'

if len(sys.argv) == 1:
  sys.stderr.write('Error[701] ::: Usage: tfstate2inventory_v3.py [mandatory:<url>|<file>] [optional:floating|fixed] [optional:<nic index>]\nFirst argument is the path or the URL to terraforma state file. Second, optional argument is the word "floating" or "fixed" that defines which IP address is going to be used to generate inventory. Third optional argument is the index of the NIC that is going to be used for remote communication by ansible (in case of multiple networks attached to a host). Defaults to 0 which is the first NIC of the host.\n')
  sys.exit(701)
elif len(sys.argv) == 4:
  if sys.argv[2] != 'floating' and sys.argv[2] != 'fixed':
    sys.stderr.write('Error[702] ::: Usage: tfstate2inventory_v3.py [mandatory:<url>|<file>] [optional:floating|fixed]  [optional:<nic index>]\nSecond argument must be one of [floating|fixed]. Third the index of the NIC that is going to be used for remote communication.\n')
    sys.exit(702)
  else:
    TERRAFORMSTATELOCATION = sys.argv[1]
    iptype = sys.argv[2]
    nic = sys.argv[3]
elif len(sys.argv) == 3:
  if sys.argv[2] != 'floating' and sys.argv[2] != 'fixed':
    sys.stderr.write('Error[702] ::: Usage: tfstate2inventory_v3.py [mandatory:<url>|<file>] [optional:floating|fixed]  [optional:<nic index>]\nSecond argument must be one of [floating|fixed]. Third the index of the NIC that i going to be used for remote communication. Usually a number between 0-2.\n')
    sys.exit(702)
  else:
    TERRAFORMSTATELOCATION = sys.argv[1]
    iptype = sys.argv[2]
    nic = 0
else:
  TERRAFORMSTATELOCATION = sys.argv[1]
  iptype = 'floating'
  nic = 0

if TERRAFORMSTATELOCATION.startswith('http://') or TERRAFORMSTATELOCATION.startswith('https://'):
  urlelement = urllib.parse.urlparse(TERRAFORMSTATELOCATION)
  hostname = urlelement[1].split(':')
  try:
    gethostbyname(hostname[0])
  except gaierror as se:
    sys.stderr.write('Error[703] ::: Could not resolve hostname ['+hostname[0]+']. Please check for typos or dns resolving issues. Reason: '+se.strerror+'\n')
    sys.exit(703)
  try:
    urllib.request.urlretrieve(TERRAFORMSTATELOCATION, 'terraform.tfstate')
  except (URLError,HTTPError,ContentTooShortError) as urle:
    sys.stderr.write('Error[704] ::: Error during retrieval of remote terraform state file from ['+TERRAFORMSTATELOCATION+']. Reason: '+urle.reason+'\n')
    sys.exit(704)
  TERRAFORMSTATEFILE = 'terraform.tfstate'
else:
  TERRAFORMSTATEFILE = TERRAFORMSTATELOCATION

if os.path.exists(TERRAFORMSTATEFILE) and os.access(TERRAFORMSTATEFILE, os.R_OK):
  try:
    tfstatejson = subprocess.Popen(["./terraform","show","-json",TERRAFORMSTATEFILE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  except subprocess.CalledProcessError as sperr:
    sys.stderr.write('Error[705] ::: Error when executing terraform command.\n'+sperr.output+'\n')
    sys.exit(705)
else:
  sys.stderr.write('Error[706] ::: Input file ['+TERRAFORMSTATEFILE+'] could not be found or read.\n')
  sys.exit(706)

cmdout,cmderr = tfstatejson.communicate()
cmdrc = tfstatejson.returncode
if cmdrc != 0:
  sys.stderr.write('Error[707] ::: Error when executing terraform command.\n'+cmdout.decode('ascii')+cmderr.decode('ascii')+'\n')
  sys.exit(707)

terraformstate = json.loads(cmdout)

# Populate list of recourses with the resources created in the root module.
try:
  for resource_index in range(len(terraformstate['values']['root_module']['resources'])):
    try:
      if 'openstack_compute_instance_v2' in terraformstate['values']['root_module']['resources'][resource_index]['address']:
        computeresourceattr = {}
        computeresourceattr['id'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['id']
        computeresourceattr['metadata_cluster'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['cluster']
        if 'ansible_extra_groups' in terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata'] and terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_extra_groups']:
          computeresourceattr['metadata_ansible_extra_groups'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_extra_groups']
        if 'ansible_port' in terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']:
          computeresourceattr['metadata_ansible_port'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_port']
        if 'ansible_user' in terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']:
          computeresourceattr['metadata_ansible_user'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_user']
        if 'ansible_ssh_private_key_file' in terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']:
          computeresourceattr['metadata_ansible_ssh_private_key_file'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['metadata']['ansible_ssh_private_key_file']
        computeresourceattr['name'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['name']
        try:
          computeresourceattr['network.0.fixed_ip_v4'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['network'][int(nic)]['fixed_ip_v4']
        except IndexError:
          sys.stderr.write('INFO ::: NIC with index '+nic+' does not exist on host with id '+computeresourceattr['id']+'. Auto revert index to 0..\n')
          computeresourceattr['network.0.fixed_ip_v4'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['network'][0]['fixed_ip_v4']
        allcomputeresourcesattr.append(computeresourceattr)
      elif 'openstack_compute_floatingip_associate_v2' in terraformstate['values']['root_module']['resources'][resource_index]['address']:
        floatingresourceattr = {}
        floatingresourceattr['instance_id'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['instance_id']
        floatingresourceattr['floating_ip'] = terraformstate['values']['root_module']['resources'][resource_index]['values']['floating_ip']
        allfloatingresourcesattr.append(floatingresourceattr)
    except KeyError:
      sys.stderr.write('INFO ::: Root module with no data found.\n')
except KeyError:
  sys.stderr.write('INFO ::: No root module resources found.\n')

# Populate list of recourses with the resources created in child modules.
try:
  for resource_index in range(len(terraformstate['values']['root_module']['child_modules'])):
    try:
      for child_resource_index in range(len(terraformstate['values']['root_module']['child_modules'][resource_index]['resources'])):
        if 'openstack_compute_instance_v2' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['address']:
          computeresourceattr = {}
          computeresourceattr['id'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['id']
          computeresourceattr['metadata_cluster'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['cluster']
          if 'ansible_extra_groups' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata'] and terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_extra_groups']:
            computeresourceattr['metadata_ansible_extra_groups'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_extra_groups']
          if 'ansible_port' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']:
            computeresourceattr['metadata_ansible_port'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_port']
          if 'ansible_user' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']:
            computeresourceattr['metadata_ansible_user'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_user']
          if 'ansible_ssh_private_key_file' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']:
            computeresourceattr['metadata_ansible_ssh_private_key_file'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['metadata']['ansible_ssh_private_key_file']
          computeresourceattr['name'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['name']
          try:
            computeresourceattr['network.0.fixed_ip_v4'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['network'][int(nic)]['fixed_ip_v4']
          except IndexError:
            sys.stderr.write('INFO ::: NIC with index '+nic+' does not exist on host with id '+computeresourceattr['id']+'. Auto revert index to 0..\n')
            computeresourceattr['network.0.fixed_ip_v4'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['network'][0]['fixed_ip_v4']
          allcomputeresourcesattr.append(computeresourceattr)
        elif 'openstack_compute_floatingip_associate_v2' in terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['address']:
          floatingresourceattr = {}
          floatingresourceattr['instance_id'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['instance_id']
          floatingresourceattr['floating_ip'] = terraformstate['values']['root_module']['child_modules'][resource_index]['resources'][child_resource_index]['values']['floating_ip']
          allfloatingresourcesattr.append(floatingresourceattr)
    except KeyError:
      sys.stderr.write('INFO ::: Module with no data found.\n')
except KeyError:
  sys.stderr.write('INFO ::: No child module resources found.\n')

for cres in range(len(allcomputeresourcesattr)):
  for fres in range(len(allfloatingresourcesattr)):
    if allcomputeresourcesattr[cres]['id'] == allfloatingresourcesattr[fres]['instance_id']:
      allcomputeresourcesattr[cres]['floating_ip'] = allfloatingresourcesattr[fres]['floating_ip']

inventory = {}
inventory['all'] = {}
inventory['all']['children'] = {}

for indexc in range(len(allcomputeresourcesattr)):
  sshport = None
  sshuser = None
  sshkey = None
  extragroups = None
  name = allcomputeresourcesattr[indexc]['name']
  try:
    floatingip = allcomputeresourcesattr[indexc]['floating_ip']
  except KeyError:
    sys.stderr.write('INFO ::: No floating ip key exists on compute instance resources list.\n')
    floatingip = None
  fixedip = allcomputeresourcesattr[indexc]['network.0.fixed_ip_v4']
  group = allcomputeresourcesattr[indexc]['metadata_cluster']
  if 'metadata_ansible_port' in allcomputeresourcesattr[indexc]:
    sshport = allcomputeresourcesattr[indexc]['metadata_ansible_port']
  if 'metadata_ansible_user' in allcomputeresourcesattr[indexc]:
    sshuser = allcomputeresourcesattr[indexc]['metadata_ansible_user']
  if 'metadata_ansible_ssh_private_key_file' in allcomputeresourcesattr[indexc]:
    sshkey = allcomputeresourcesattr[indexc]['metadata_ansible_ssh_private_key_file']
  if 'metadata_ansible_extra_groups' in allcomputeresourcesattr[indexc]:
    extragroups = allcomputeresourcesattr[indexc]['metadata_ansible_extra_groups'].split(',')
  if group in inventory['all']['children']:
    inventory['all']['children'][group]['hosts'][name] = {}
    if iptype == 'floating':
      inventory['all']['children'][group]['hosts'][name]['ansible_host'] = floatingip
    elif iptype == 'fixed':
      inventory['all']['children'][group]['hosts'][name]['ansible_host'] = fixedip
    if sshport:
      inventory['all']['children'][group]['hosts'][name]['ansible_port'] = int(sshport)
    if sshuser:
      inventory['all']['children'][group]['hosts'][name]['ansible_user'] = sshuser
    if sshkey:
      inventory['all']['children'][group]['hosts'][name]['ansible_ssh_private_key_file'] = sshkey
  else:
    inventory['all']['children'][group] = {}
    inventory['all']['children'][group]['hosts'] = {}
    inventory['all']['children'][group]['hosts'][name] = {}
    if iptype == 'floating':
      inventory['all']['children'][group]['hosts'][name]['ansible_host'] = floatingip
    elif iptype == 'fixed':
      inventory['all']['children'][group]['hosts'][name]['ansible_host'] = fixedip
    if sshport:
      inventory['all']['children'][group]['hosts'][name]['ansible_port'] = int(sshport)
    if sshuser:
      inventory['all']['children'][group]['hosts'][name]['ansible_user'] = sshuser
    if sshkey:
      inventory['all']['children'][group]['hosts'][name]['ansible_ssh_private_key_file'] = sshkey
  if extragroups:
    for secgroup in extragroups:
      if secgroup in inventory['all']['children']:
        inventory['all']['children'][secgroup]['hosts'][name] = {}
        if iptype == 'floating':
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_host'] = floatingip
        elif iptype == 'fixed':
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_host'] = fixedip
        if sshport:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_port'] = int(sshport)
        if sshuser:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_user'] = sshuser
        if sshkey:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_ssh_private_key_file'] = sshkey
      else:
        inventory['all']['children'][secgroup] = {}
        inventory['all']['children'][secgroup]['hosts'] = {}
        inventory['all']['children'][secgroup]['hosts'][name] = {}
        if iptype == 'floating':
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_host'] = floatingip
        elif iptype == 'fixed':
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_host'] = fixedip
        if sshport:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_port'] = int(sshport)
        if sshuser:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_user'] = sshuser
        if sshkey:
          inventory['all']['children'][secgroup]['hosts'][name]['ansible_ssh_private_key_file'] = sshkey

with open('hosts', 'w') as outfile:
  print(yaml.safe_dump(inventory, outfile, default_flow_style=False))
print(yaml.safe_dump(inventory, default_flow_style=False))
