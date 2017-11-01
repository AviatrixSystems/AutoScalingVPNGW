## Aviatrix Auto Scaling VPN Gateway

### Description
This script auto scales Aviatrix VPN GWs launched in ELBs.

### Prerequisite
1. Make sure you have a running controller. For instructions on how to launch a new controller go to https://github.com/AviatrixSystems/AWSQuickStart


### Step by step Procedure:

1. Download this repository as zip file, by clicking on top right green button named `Clone or download`, and then click on `Download ZIP`.

2. Extract the downloaded zipped file on your local system. You will get a directory named `AutoScalingVPNGW-master`. Inside this directory, there will be a zipped file named `aviatrix_vpn_scale.zip`.

3. Create an S3 bucket of any name(for eg. aviatrix_lambda). Note down this bucket's name, this will be required later in cloud formation. Upload `aviatrix_vpn_scale.zip` to this S3 bucket.

4. Go to AWS Console-> Services -> Management Tools-> CloudFormation.

5. On CloudFormation page, Select Create stack.

6. On the next screen, Select `Upload a template to Amazon S3`. Click on `Choose file`, and then select `aviatrix_vpn_scale_cft.json` from directory `AutoScalingVPNGW-master` created in Step 2.

7. Click next.

8. On the Stack Name textbox, Name your Stack -> Something like *AviatrixVPNScale*

9. Enter the parameters as per description. Click next.

10. Specify your options/tags/permissions as per your policies, when in doubt just click next.

11. On the review page, scroll to the bottom and check the button that reads:
*I acknowledge that AWS CloudFormation might create IAM resources with custom names.*

12. Click on Create.

13. Wait for status to change to `CREATE_COMPLETE`. If fails, debug or contact Aviatrix support.

14. Enjoy! You are welcome!
