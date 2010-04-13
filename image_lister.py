#!/usr/bin/env python

from sugar.datastore import datastore
import sys
import shutil

def get_images():
    rtn = []
    (results,count) = datastore.find(dict(mime_type="image/png"))
    for f in results:
        dict = f.get_metadata().get_dictionary()
        if dict["mime_type"] == "image/png":
              rtn.append(f.object_id)
        f.destroy()
    return rtn

if __name__ == '__main__':
    imagelist = get_images()
    for i in imagelist:
        print('\n%s'%i)