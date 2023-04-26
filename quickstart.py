from __future__ import print_function

import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

# 'Z' indicates UTC time
def makeDateString(date):
    return date.isoformat() + 'Z'


# parses calendarIds to Object for google
def makeIdsObject(ids):
    idsObject = []
    for id in ids:
        idsObject.append({"id":id})
    return idsObject


# returns time at 00:00 on the same date
def getNearStartTime():
    return datetime.datetime.utcnow().replace(hour=00,minute=00,second=00)

def timeInBlock(time, block):
    if block['end'] == float('inf'): return False
    return block['start'] <= time and block['end'] >= time

def sortAllBusy(busy_all):
    blocks = []  # will store all busy blocks where one can not work

    # Loop blocks all times in from 19 to 8 (over night)
    for i in range(7):
        night_event = {'start': makeDateString(getNearStartTime().replace(hour=17,minute=00,second=00)+datetime.timedelta(days=i)),'end': makeDateString(getNearStartTime().replace(hour=6,minute=00,second=00)+datetime.timedelta(days=i+1))}
        busy_all.append(night_event)
    
    # messy loop that merges overlapping events into blocks
    # and sorts the blocks
    # TODO make loop not messy
    for event in busy_all:
        start = datetime.datetime.fromisoformat(event['start'][:-1])
        end = datetime.datetime.fromisoformat(event['end'][:-1])
        found = False
        for i,block in enumerate(blocks):
            between_block = {'start': getNearStartTime() if i == 0 else blocks[i-1]['start'],'end':blocks[i]['start']}
            if timeInBlock(start,between_block) and timeInBlock(end,between_block):
                blocks.insert(i,{'start':start,'end':end})
                found = True
                break
            if timeInBlock(start,block):
                if block['end'] < end:
                    block['end'] = end
                found = True
            if timeInBlock(end,block):
                if block['start'] > start:
                    block['start'] = start
                found = True
        if not found:
            blocks.append({'start': start,'end':end})
    print('fin')
    return blocks


def getAllBusy(dateStart,ids,service):

    # API CALL TO GET BUSYNESS
    body = {
        'timeMin': makeDateString(dateStart),
        'timeMax': makeDateString(dateStart + datetime.timedelta(days=7)),
        'timeZone': 'GMT',
        'items':
            makeIdsObject(ids)
    }
    events_result = service.freebusy().query(body=body).execute()

    # merge calendars into one array
    # might actually be super useless
    # TODO check if this is super useless
    cal_dict = events_result['calendars']
    busy_all= []
    for cal_name in cal_dict:
        print(cal_name,cal_dict[cal_name])
        busy_all += cal_dict[cal_name]['busy']
    return sortAllBusy(busy_all)

def getPossibleWorkTime(blocks):
    work_time = []
    for i,block in enumerate(blocks):
        if i == 0: continue
        if block['start'] - blocks[i-1]['end'] > datetime.timedelta(minutes=15) and block['start'].weekday() != 5 and block['start'].weekday() != 6:
            work_time.append({'start': blocks[i-1]['end'],'end': block['start']})
    return work_time

def main():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)
        # Call the Calendar API
        now = getNearStartTime()
        now_string = makeDateString(now)
        
        calendars = service.calendarList().list().execute().get('items',[])
        calendar_ids = []
        events = []
        for calendar in calendars:
            if calendar['summary'] == 'Arbeit':
                work_calendar_id = calendar['id']
            calendar_ids.append(calendar.get('id',[]))
            events += service.events().list(calendarId=calendar.get('id',[]),timeMin = now_string,timeMax = makeDateString(now +datetime.timedelta(days=7)),singleEvents=True,orderBy='startTime').execute().get('items',[])
        work_blocks = getPossibleWorkTime(getAllBusy(now,calendar_ids,service))
        for i in work_blocks:
            # print(i['start'].date(),i['start'].time(),':',i['end'].date(),i['end'].time())
            event = service.events().insert(calendarId=work_calendar_id, body={'summary':'AUTO-CALCED','start':{'dateTime':makeDateString(i['start'])},'end': {'dateTime':makeDateString(i['end'])}}).execute()
            print(event.get('htmlLink'))

    except HttpError as error:
        print('An error occurred: %s' % error)


if __name__ == '__main__':
    main()