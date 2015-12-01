#!/usr/bin/python
#
# This is a free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This Ansible library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = """
---
module: ec2_vpc_dhcp_options_set
short_description: create or remove a dhcp options set
description:
    - create or remove a dhcp options set
version_added: "2.1"
author: Kristian Jones (@klj613)
options:
  name:
    description:
      - Unique name of the DHCP option set
    required: true
  domain:
    description:
      - Domain value used in the DHCP option set
    required: false
    default: null
  domain_name_servers:
    description:
      - List of the domain name servers to be set in the DHCP option set
    required: false
    default: null
  ntp_servers:
    description:
      - List of the NTP servers to be set in the DHCP option set
    required: false
    default: null
  netbios_name_servers:
    description:
      - List of the netbios name servers to be set in the DHCP option set
    required: false
    default: null
  netbios_node_type:
    description:
      - The node type of the netbios name servers to be set in the DHCP option set
    required: false
    default: null
  region:
    description:
      - The AWS region to use.  Must be specified if ec2_url is not used. If not specified then the value of the EC2_REGION environment variable, if any, is used.
    required: false
    default: null
    aliases: ['aws_region', 'ec2_region']
  aws_secret_key:
    description:
      - AWS secret key. If not set then the value of the AWS_SECRET_KEY environment variable is used.
    required: false
    default: None
    aliases: ['ec2_secret_key', 'secret_key']
  aws_access_key:
    description:
      - AWS access key. If not set then the value of the AWS_ACCESS_KEY environment variable is used.
    required: false
    default: None
    aliases: ['ec2_access_key', 'access_key']

requirements: [ "boto" ]
"""

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# Basic creation example:
- name: Set up public subnet route table
  ec2_vpc_dhcp_options_set:
    name: 'options-set-name'
    region: eu-west-1
    domain: hq.mycorp.net
    domain_name_servers: ['172.30.0.1', '172.30.0.2']
    ntp_servers: ['172.30.0.1', '172.30.0.2']
    netbios_name_servers: ['172.30.0.1', '172.30.0.2']
    netbios_node_type: 2
  register: dhcp_options_set
'''

RETURN = '''
dhcp_options_set_id:
    description: the id of the dhcp options set
    returned: success
    sample: dopt-d0a543b5
'''

import sys

try:
    import boto.ec2
    import boto.vpc
    import boto.exception
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

if not HAS_BOTO:
    module.fail_json(msg='boto required for this module')

def build_options(domain, domain_name_servers, ntp_servers,
        netbios_name_servers, netbios_node_type):
    """
    Build a dict of the options to compare with other dicts

    domain: the domain
    domain_name_servers: list of the dns servers
    ntp_servers: list of the ntp servers
    netbios_name_servers: list of the netbios servers
    netbios_node_type: node type of the netbios servers
    """

    optionsdict = {}

    if domain != None:
        optionsdict['domain-name'] = [domain]
    if domain_name_servers != None:
        optionsdict['domain-name-servers'] = domain_name_servers
    if ntp_servers != None:
        optionsdict['ntp-servers'] = ntp_servers
    if netbios_name_servers != None:
        optionsdict['netbios-name-servers'] = netbios_name_servers
    if netbios_node_type != None:
        optionsdict['netbios-node-type'] = [str(netbios_node_type)]

    return optionsdict

def create_dhcp_options_set(module, ec2, vpc_conn):
    """
    Created a dhcp options set and assosiates it with a VPC

    module: Ansible module object
    ec2: authenticated ec2 connection object
    vpc_conn: authenticated VPCConnection connection object
    name: the option set name
    domain: the domain
    domain_name_servers: list of the dns servers
    ntp_servers: list of the ntp servers
    netbios_name_servers: list of the netbios servers
    netbios_node_type: node type of the netbios servers

    Returns a tuple
    """
    name = module.params.get('name')
    domain = module.params.get('domain')
    domain_name_servers = module.params.get('domain_name_servers')
    ntp_servers = module.params.get('ntp_servers')
    netbios_name_servers = module.params.get('netbios_name_servers')
    netbios_node_type = module.params.get('netbios_node_type')

    dhcp_options = vpc_conn.get_all_dhcp_options()

    for dhcp_option in dhcp_options:
        filters = {'resource-id': dhcp_option.id}
        gettags = ec2.get_all_tags(filters=filters)
        tagdict = {}
        for tag in gettags:
            tagdict[tag.name] = tag.value

        if ('Name', name) in set(tagdict.items()):
            real_options = dhcp_option.options
            desired_options = build_options(domain, domain_name_servers, ntp_servers,
                netbios_name_servers, netbios_node_type)

            if desired_options != real_options:
                module.fail_json(msg='DHCP options cannot be modified')

            return (dhcp_option.id, False)

    dhcp_options_set = vpc_conn.create_dhcp_options(domain, domain_name_servers,
            ntp_servers, netbios_name_servers, netbios_node_type)
    ec2.create_tags(dhcp_options_set.id, {'Name': name})

    return (dhcp_options_set.id, True)

def delete_dhcp_options_set(module, ec2, vpc_conn):
    """
    Deleted a DHCP options set

    module: Ansible module object
    ec2: authenticated ec2 connection object
    vpc_conn: authenticated VPCConnection connection object
    name: the option set name

    Returns a list of the DHCP options that have been deleted
    """

    name = module.params.get('name')

    dhcp_options = vpc_conn.get_all_dhcp_options()
    removed_dhcp_options = []

    for dhcp_option in dhcp_options:
        filters = {'resource-id': dhcp_option.id}
        gettags = ec2.get_all_tags(filters=filters)
        tagdict = {}
        for tag in gettags:
            tagdict[tag.name] = tag.value

        if ('Name', name) in set(tagdict.items()):
            vpc_conn.delete_dhcp_options(dhcp_option.id)

            removed_dhcp_options.append(dhcp_option.id)
    
    return removed_dhcp_options

def main():
    """
    Module entry point.
    """
    arguent_spec = ec2_argument_spec()
    arguent_spec.update(dict(
        name=dict(required=True),
        domain=dict(required=False),
        domain_name_servers=dict(default=None, required=False, type='list'),
        ntp_servers=dict(default=None, required=False, type='list'),
        netbios_name_servers=dict(default=None, required=False, type='list'),
        netbios_node_type=dict(default=None, required=False, type='int'),
        state=dict(choices=['present', 'absent'], default='present'),
        ))

    module = AnsibleModule(
        argument_spec=arguent_spec,
    )

    state = module.params.get('state')
    _, aws_access_key, aws_secret_key, region = get_ec2_creds(module)

    if region:
        try:
            vpc_conn = boto.vpc.connect_to_region(
                region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )

            ec2 = ec2_connect(module)
        except boto.exception.NoAuthHandlerFound, ex:
            module.fail_json(msg=str(ex))
    else:
        module.fail_json(msg="region must be specified")

    if state == 'present':
        (dhcp_options_set_id, changed) = create_dhcp_options_set(module, ec2, vpc_conn)
        module.exit_json(changed=changed, dhcp_options_set_id=dhcp_options_set_id)
    elif state == 'absent':
        removed = delete_dhcp_options_set(module, ec2, vpc_conn)
        changed = (len(removed) > 0)
        module.exit_json(changed=changed)

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *
main()
