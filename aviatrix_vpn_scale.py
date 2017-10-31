import os
import sys
import requests
import boto3
import uuid
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
import urllib2

MAX_VPN_USERS_ALLOWED = 3

def get_elb_name(elb_dns_name):
    elb_dns_split = elb_dns_name.split("-")
    if elb_dns_split[0] == 'Aviatrix':
        elb_name = "-".join(elb_dns_split[0:3])
    else:
        elb_name = elb_dns_split[0]
    return elb_name

def get_avtx_elb(aviatrixElbList, vpc_id=None, gw_name=None):
    if vpc_id:
        for avtx_elb in aviatrixElbList:
            if avtx_elb.vpc_id == vpc_id:
                return avtx_elb
    if gw_name:
        for avtx_elb in aviatrixElbList:
            if gw_name in avtx_elb.gws:
                return avtx_elb

    return None

class AviatrixElb:
    def __init__(self, elb_name, account_name, vpc_id, vpc_region, split_tunnel):
        self.elb_name = elb_name
        self.account_name = account_name
        self.vpc_id = vpc_id
        self.vpc_region = vpc_region
        self.split_tunnel = split_tunnel
        self.gws = []
        self.subnets = []
        self.num_vpn_gws = 0
        self.num_live_vpn_users = 0

class AviatrixAPI:
    def __init__(self, controller_eip, aviatrix_user, aviatrix_pass):
        self.base_url = "https://"+controller_eip+"/v1/api"
        self.cid = ''
        self.aviatrix_user = aviatrix_user
        self.aviatrix_pass = aviatrix_pass
        self.aviatrixElbList = []

    def login(self):
        def createSessionSuccessCb(response_json):
            try:
                self.cid = response_json['CID']
                print("Created new session with CID %s\n" %self.cid)
            except KeyError, e:
                print("Unable to create session. %s" %str(e))
                raise
        args = 'action=login&username=' + self.aviatrix_user + '&password=' + self.aviatrix_pass
        #print "Creating new session with username.... "
        self.do_get(args, createSessionSuccessCb)

    def populateAvtxElbs(self):
        def populateAvtxElbsCb(response_json):
            #gw_list = ''
            try:
                gw_list = response_json['results']
            except KeyError, e:
                print("Unable to get GW List. %s" %str(e))
                raise
        
            for gw in gw_list:
                if gw['elb_dns_name']:
                    #print "elb_dns_name-> "+gw['elb_dns_name']
                    elb_name = get_elb_name(gw['elb_dns_name'])
                    #print elb_name
                    avtx_elb = get_avtx_elb(self.aviatrixElbList, vpc_id=gw['vpc_id'])

                    if avtx_elb is None:
                        avtx_elb = AviatrixElb(elb_name, gw['account_name'], gw['vpc_id'], gw['vpc_region'], gw['split_tunnel'])
                        avtx_elb.num_vpn_gws = 1
                        avtx_elb.gws.append(gw['vpc_name'])
                        avtx_elb.subnets.append(gw['gw_subnet_id'])
                        self.aviatrixElbList.append(avtx_elb)
                    else:
                        avtx_elb.num_vpn_gws += 1
                        avtx_elb.gws.append(gw['vpc_name'])
                        avtx_elb.subnets.append(gw['gw_subnet_id'])


        args = 'CID='+self.cid+'&action=list_vpcs_summary&account_name='+self.aviatrix_user
        self.do_get(args, populateAvtxElbsCb)

    def getLiveVPNUserCnt(self):
        def getLiveVPNUserCntCb(response_json):
            try:
                vpn_users_list = response_json['results']
            except KeyError, e:
                print("Unable to get Live VPN Users List. %s" %str(e))
                raise

            for user in vpn_users_list:
                avtx_elb = get_avtx_elb(self.aviatrixElbList, gw_name=user['gateway_name'])
                avtx_elb.num_live_vpn_users += 1

        args = 'CID='+self.cid+'&action=list_live_vpn_users'
        self.do_get(args, getLiveVPNUserCntCb)

    def launchVpnGw(self, avtx_elb):
        def launchVpnGwCb(response_json):
            try:
                print("VPN gateway Creation Successful %s" %response_json['results'])
            except KeyError, e:
                print("Unable to create VPC/gateway.")
                raise

        client = boto3.client('ec2', avtx_elb.vpc_region)
        vpn_gw_subnet = avtx_elb.subnets[0]
        vpn_gw_split_tunnel = avtx_elb.split_tunnel
        auto_vpn_gw_name = "auto-vpn-gw-" + uuid.uuid4().hex[-10:]
        print(auto_vpn_gw_name)
        vpn_gw_subnet_cidr = client.describe_subnets(SubnetIds=[vpn_gw_subnet]).get('Subnets')[0].get('CidrBlock')
        data = {"CID": self.cid, "action": "connect_container", "cloud_type": 1, "account_name": avtx_elb.account_name, "gw_name": auto_vpn_gw_name, "vpc_id": avtx_elb.vpc_id, "vpc_reg": avtx_elb.vpc_region, "vpc_net": vpn_gw_subnet_cidr, "vpc_size": "t2.micro", "vpn_access": "yes", "cidr": "192.168.43.0/24", "enable_elb": "yes", "split_tunnel": vpn_gw_split_tunnel}
        print("Creating VPC...")
        self.do_post(data, launchVpnGwCb)

    def do_get(self, args, callback=None):
        url = self.base_url+'?'+args
        print(url)
        try:
            response = requests.get(url, verify=False)
        except Exception, e:
            print("Unable to establish connection.")
            raise        
        response_json = response.json()
        print(response_json)

        if callback:
            if response_json['return'] == True:
                return callback(response_json)
            else:
                print("Failed: %d error - %s" %(response.status_code, str(response_json['reason'])))
                raise Exception("Get request error.")
        

    def do_post(self, data, callback):
        try:
            response = requests.post(self.base_url, data=data, verify=False)
        except Exception, e:
            print("Unable to establish connection.")
            raise
        response_json = response.json()
        if response_json['return'] == True:
            return callback(response_json)
        else:
            print("Failed: %d error - %s" %(response.status_code, str(response_json['reason'])))
            raise Exception("Post request error.")


def lambda_handler(event, context):
    CONTROLLER_EIP = os.environ.get('CONTROLLER_EIP')
    AVIATRIX_USER = os.environ.get('AVIATRIX_USER')
    AVIATRIX_PASS = urllib2.quote(os.environ.get('AVIATRIX_PASS'), '%')
    aviatrix_api= AviatrixAPI(CONTROLLER_EIP, AVIATRIX_USER, AVIATRIX_PASS)
    aviatrix_api.login()
    aviatrix_api.populateAvtxElbs()
    aviatrix_api.getLiveVPNUserCnt()
    for avtx_elb in aviatrix_api.aviatrixElbList:
        if avtx_elb.num_live_vpn_users > 0 and avtx_elb.num_vpn_gws/avtx_elb.num_live_vpn_users > MAX_VPN_USERS_ALLOWED:
        #if True:
            aviatrix_api.launchVpnGw(avtx_elb)

    #aviatrix_api.do_get('CID='+aviatrix_api.cid+'&action=list_vpcs_summary&account_name='+aviatrix_api.aviatrix_user)
    #aviatrix_api.do_get('CID='+aviatrix_api.cid+'&action=list_live_vpn_users')
