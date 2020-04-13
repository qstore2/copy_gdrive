from __future__ import print_function

import re
import sys
import codecs
import argparse
import pickle
import os.path
import time
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER = 'application/vnd.google-apps.folder'


re_fileid = re.compile('[-_\w]{25,}')
re_match1 = re.compile('file/d/([^/]*)')
re_match2 = re.compile('id=([^&]*)')
def getid(url):
    if re_fileid.match(url):
        return url
    try:
        return re_match1.search(url).group(1)
    except:
        try:
            return re_match2.search(url).group(1)
        except Exception as e:
            raise e


def get_service(path):
    """Login to Drive v3 API.
    """
    global service
    creds = None

    if args.service_account_file:
        creds = service_account.Credentials.from_service_account_file(args.service_account_file)
    else:
        tokenfile = os.path.join(path, 'token.pickle')
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(tokenfile):
            with open(tokenfile, 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(os.path.join(path, 'credentials.json'), SCOPES)
                # creds = flow.run_local_server()
                creds = flow.run_console()
            # Save the credentials for the next run
            with open(tokenfile, 'wb') as token:
                pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)


delay=1
lastcall=0
def googlesleep():
    """Call only when userRateLimitExceeded"""
    global delay,lastcall
    if time.time()-lastcall > min(delay+1,10):
        delay = 1
    else:
        delay = min(delay*1.5, 120)
    print("userRateLimitExceeded, sleeping for %f sec"%(delay))
    time.sleep(delay)
    lastcall=time.time()


def trygoogleapi(func, **kwargs):
    while True:
        try:
            return func(**kwargs).execute()
            break
        except HttpError as e:
            print("Error:" + str(e.content), file=sys.stderr)
            if 'userRateLimitExceeded' in str(e.content):
                googlesleep()
            else:
                raise e


def getfiles(source):
    if source['mimeType'] == FOLDER:
        nextPageToken = ''
        while True:
            results = trygoogleapi(service.files().list, pageSize=1000,
                                   fields="nextPageToken, files(id, name, mimeType)",
                                   supportsAllDrives=True, includeItemsFromAllDrives=True,
                                   pageToken=nextPageToken, q="'"+source['id']+"' in parents and trashed = false")
            yield from results['files']
            if not 'nextPageToken' in results: break
            nextPageToken = results['nextPageToken']
            # try:
            #     results = service.files().list(pageSize=1000, fields="nextPageToken, files(id, name, mimeType)",
            #                                supportsAllDrives=True, includeItemsFromAllDrives=True,
            #                                pageToken=nextPageToken, q="'"+source['id']+"' in parents and trashed = false").execute()
            #     yield from results['files']
            #     if not 'nextPageToken' in results: break
            #     nextPageToken = results['nextPageToken']
            # except HttpError as e:
            #     print("Error:"+str(e.content))
            #     if 'userRateLimitExceeded' in str(e.content):
            #         googlesleep()
            #     else:
            #         raise e


def getsubdir(name, destid):
    results = trygoogleapi(service.files().list, supportsAllDrives=True, includeItemsFromAllDrives=True,
                           q="'" + destid + "' in parents and name='"+str(name).replace("'","\\'")+
                           "' and mimeType='"+FOLDER+"' and trashed = false")
    if results['files']:
        return results['files'][0]['id']
    result = trygoogleapi(service.files().create, supportsAllDrives=True,
                          body={'name': name, 'parents': [destid], 'mimeType': FOLDER})
    return result['id']
    # while True:
    #     try:
    #         results = service.files().list(supportsAllDrives=True, includeItemsFromAllDrives=True,
    #                                        q="'" + destid + "' in parents and name='"+str(name).replace("'","\\'")+
    #                                          "' and mimeType='"+FOLDER+"' and trashed = false").execute()
    #         if results['files']:
    #             return results['files'][0]['id']
    #         break
    #     except HttpError as e:
    #         print("Error:"+str(e.content))
    #         if 'userRateLimitExceeded' in str(e.content):
    #             googlesleep()
    #         else:
    #             raise e
    # result = service.files().create(supportsAllDrives=True,
    #                                 body={'name': name, 'parents': [destid], 'mimeType': FOLDER}).execute()
    # return result['id']


def copyitem(source, destid, root=False):
    if source['mimeType'] == FOLDER:
        if not root: destid = getsubdir(source['name'], destid)
        for item in getfiles(source):
            copyitem(item, destid)
    else:
        r = service.files().copy(fileId=source['id'], supportsAllDrives=True, body={"parents":[destid]}).execute()
        # print(r)


def copy(sourceid, destid):
    file = trygoogleapi(service.files().get, fileId=sourceid, supportsAllDrives=True)
    copyitem(file, destid, True)
    if 'name' in file:
        return file['name']


def getdriveid(name):
    if name == 'root' or name == '': return 'root'

    #find by id
    if re.match("^[-_\w]+$", name):
        try:
            drive = trygoogleapi(service.drives().get, driveId=name)
            if drive:
                return drive['id']
        except:
            pass

    #find by name
    nextPageToken = ''
    while True:
        results = trygoogleapi(service.drives().list, pageSize=100, pageToken=nextPageToken)
        for drive in results['drives']:
            if name == drive['name']:
                return drive['id']
        if not 'nextPageToken' in results: break
        nextPageToken = results['nextPageToken']


def getfolderid(path):
    drive, path = path.split(":", 1)
    folderid = getdriveid(drive)
    if folderid is None: raise Exception('Cannot find drive: '+drive)
    parts = os.path.normpath(path).lstrip(os.sep).split(os.sep)
    # print(parts)
    for part in parts:
        folderid = getsubdir(part, folderid)
        # print(folderid)
    return folderid


if __name__ == '__main__':
    # sys.stdout = codecs.getwriter('utf8')(sys.stdout.buffer)
    parser = argparse.ArgumentParser("Copy files from gdrive shared links")
    parser.add_argument("url", help="Shared link")
    parser.add_argument("path", help="Where to paste")
    parser.add_argument("--config", help="Path to credentials.json", default=".")
    parser.add_argument("--service-account-file", help="Service Account Credentials JSON file path")
    args = parser.parse_args()

    fileid=getid(args.url)
    get_service(args.config)
    # print(args.path)
    folderid = getfolderid(args.path)
    # print(folderid)
    filename=copy(fileid, folderid)
    print("File copied over: "+filename + " ("+args.url+")")
