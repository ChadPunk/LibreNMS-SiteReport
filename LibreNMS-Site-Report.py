import requests
import datetime
import jinja2 
import numpy as np
import pdfkit
import smtplib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders


# !!!!! Set LibreNMS API key and URL
api_key = 'PUT-API-KEY-HERE'
url_devices = 'http://yoururl/api/v0/devices/'
groupsurl = 'http://yoururl/api/v0/devicegroups/'

# Pass authentication token
headers = {'X-Auth-Token': api_key}

# Make API call to get list of devices
devices = requests.get(url_devices, headers=headers, verify=False)

# Make API call to get list of device groups
groups = requests.get(groupsurl, headers=headers)

# Loop through each group
results = {}
site = {}
libregroups = []

print("Conencting to LibreNMS")
print("-----------------------")
for group in groups.json()['groups']:
    site = {}
    sitetimes = []
    group_name = group['name']
    libregroups.append(group_name+'.txt')
    
    # Make API call to get details of each device in the group
    librenms_group = requests.get(groupsurl + group_name, headers=headers)
    try:
        devices_in_group = librenms_group.json()['devices']
    except KeyError:
        print(f"No devices found in group {group_name}")
        continue
    
    # Loop through each device and calculate SLA
    for device in devices_in_group:
        device_id = str(device['device_id'])
        librenms_device = requests.get(url_devices + device_id, headers=headers)
        device_info = librenms_device.json()['devices'][0]
        device_name = device_info['sysName']
        librenms_availability = requests.get(url_devices + device_id + '/availability', headers=headers)
        for time in librenms_availability.json()['availability']:
            duration = time['duration']
            # Looks for the whole year
            if duration == 31536000:
                sla = time['availability_perc']
                if float(sla) > 0:
                    sitetimes.append(f'{sla}')
                    siteDict = {device_name : sla}
                    site.update(siteDict)
    sitedatajson = json.dumps(site, indent=4)
    with open(group_name+'.txt', "w") as site_file_average:
        site_file_average.write(f'{sitedatajson}')
    # Write the average SLA for the group to a file
    sitetimes_float = [float(st) for st in sitetimes]
    mean_sla = np.mean(sitetimes_float)
    # !!!!! Can tweak this for how it averages the groups just change the 3 for the nearest dec place.
    rounded_sla = round(mean_sla, 3)
    print(f'Completed pull from Libre for {group_name}.')
    print("-----------------------")


    # Calculate the overall SLA percentage for the group
    temp_dict = {group_name: f'{rounded_sla} %'}
    results.update(temp_dict)

print("Creating report...")
print("-----------------------")
# Get Date/Time
time = datetime.datetime.now()
timeModified = time.strftime("%Y-%m-%d %H:%M:%S")
print(f"Created report! {timeModified}")
# Generate PDF report using Jinja2
# !!!!! needs to be an absoulute path to the file. Example /home/administrator/. this needs to be where the report_template file lives.
templateLoader = jinja2.FileSystemLoader(searchpath="PUT YOUR PATH HERE")
templateEnv = jinja2.Environment(loader=templateLoader)
TEMPLATE_FILE = "report_template.html"
template = templateEnv.get_template(TEMPLATE_FILE)
html = template.render(results=results, timeNow=timeModified)
filepdf = timeModified + ' Report.pdf'

pdfkit.from_string(html, filepdf)
libregroups.append(filepdf)


# !!!!! Define sender and recipient email addresses
from_addr = 'from@example.com'
to_addr = 'to@example.com'
cc_addr = ['cc1@@example.com', 'cc2@example.com']


# Create message object
msg = MIMEMultipart()
msg['From'] = from_addr
msg['To'] = to_addr
msg['Cc'] = ', '.join(cc_addr) 
msg['Subject'] = 'Email Subject name'

# !!!!! Add body text to the message
body = 'Attached is the automated Site Up-Time report.'
msg.attach(MIMEText(body, 'plain'))

# Open and attach each file
libregroups.reverse()
for filename in libregroups:
    with open(filename, 'rb') as attachment:
        # Create a MIMEBase object and set its parameters
        p = MIMEBase('application', 'octet-stream')
        p.set_payload(attachment.read())
        encoders.encode_base64(p)
        p.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(p)
# Create SMTP object and send the message
s = smtplib.SMTP('smtp.roseburg.us', 25)
s.sendmail(from_addr, [to_addr] + cc_addr, msg.as_string())
s.quit()

# Close the attachment file
attachment.close()
