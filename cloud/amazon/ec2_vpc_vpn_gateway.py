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
module: ec2_vpc_vpn_gateway
short_description: create or remove a vpn gateway
description:
    - create or remove a vpn gateway
version_added: "2.1"
author: Kristian Jones (@klj613)
options:
  name:
    description:
      - Unique name of the vpn gateway
    required: true
  vpc_id:
    description:
      - The VPC to attach to this vpn gateway
  type:
    description:
      - The type of the vpn gateway
    required: true
  state:
    description:
      - The desired state of the vpn gateway
    required: true
    choices: [ 'present', 'absent' ]
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

- name: create vpn gateway
  ec2_vpc_vpn_gateway:
    name: vgw-1
    vpc_id: 'id_of_the_vpc'
    state: present
    type: ipsec.1
  register: vgw
'''

RETURN = '''
gateway_id:
    description: the id of the vpc gateway
    returned: success
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

def create_vpn_gateway(module, ec2, vpc_conn):
    """
    Creates a vpn gateway

    module: Ansible module object
    ec2: authenticated ec2 connection object
    name: the option set name
    vpc_conn: authenticated VPCConnection connection object
    name: the option set name
    type: type of the vpn gateway

    Returns a tuple
    """
    name = module.params.get('name')
    vpc_id = module.params.get('vpc_id')
    type = module.params.get('type')

    vpn_gateways = vpc_conn.get_all_vpn_gateways()

    for vpn_gateway in vpn_gateways:
        filters = {'resource-id': vpn_gateway.id}
        gettags = ec2.get_all_tags(filters=filters)
        tagdict = {}
        for tag in gettags:
            tagdict[tag.name] = tag.value

        if ('Name', name) in set(tagdict.items()):
            changed = False
            immutable_changed = False

            attachments = vpn_gateway.attachments

            vpc_found = False
            for attachment in attachments:
                if attachment.vpc_id != vpc_id:
                    vpc_conn.detach_vpn_gateway(vpn_gateway.id, attachment.vpc_id)
                    changed = True
                else:
                    vpc_found = True

            if not vpc_found:
                vpc_conn.attach_vpn_gateway(vpn_gateway.id, vpc_id)
                changed = True

            if type != vpn_gateway.type:
                immutable_changed = True

            if immutable_changed:
                module.fail_json(msg='VPN gateway cannot be modified in that way')

            return (vpn_gateway.id, changed)

    vpn_gateway = vpc_conn.create_vpn_gateway(type)
    ec2.create_tags(vpn_gateway.id, {'Name': name})
    vpc_conn.attach_vpn_gateway(vpn_gateway.id, vpc_id)

    return (vpn_gateway.id, True)

def delete_vpn_gateway(module, ec2, vpc_conn):
    """
    Deletes a vpn gateway

    module: Ansible module object
    ec2: authenticated ec2 connection object
    vpc_conn: authenticated VPCConnection connection object
    name: the option set name

    Returns a list of the DHCP options that have been deleted
    """

    name = module.params.get('name')

    vpn_gateways = vpc_conn.get_all_vpn_gateways()
    removed_vpn_gateways = []

    for vpn_gateway in vpn_gateways:
        filters = {'resource-id': vpn_gateway.id}
        gettags = ec2.get_all_tags(filters=filters)
        tagdict = {}
        for tag in gettags:
            tagdict[tag.name] = tag.value

        if ('Name', name) in set(tagdict.items()):
            vpc_conn.delete_vpn_gateway(vpn_gateway.id)

            removed_vpn_gateways.append(vpn_gateway.id)
    
    return removed_vpn_gateways

def main():
    """
    Module entry point.
    """
    arguent_spec = ec2_argument_spec()
    arguent_spec.update(dict(
        name=dict(required=True),
        vpc_id=dict(required=True),
        type=dict(required=True),
        state=dict(choices=['present', 'absent'], default='present')
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
        (connection, changed) = create_vpn_gateway(module, ec2, vpc_conn)
        module.exit_json(changed=changed, gateway_id=connection)
    elif state == 'absent':
        removed = delete_vpn_gateway(module, ec2, vpc_conn)
        changed = (len(removed) > 0)
        module.exit_json(changed=changed, removed_ids=removed)

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *
main()
