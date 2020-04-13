# copy_gdrive
Copy files from gdrive shared links to your own gdrive


python https://drive.google.com/file/d/xxxx/view?usp=sharing [myfolderid]:dir1/dir2/


To get myfolderid, use chrome and browse to the folder, copy the last part of the url after the last slash (/)

Eg if the url is https://drive.google.com/drive/folders/0GESC_NwV67AWUc9PVA
the myfolderid is 0GESC_NwV67AWUc9PVA, then the command will be:
python https://drive.google.com/file/d/xxxx/view?usp=sharing 0GESC_NwV67AWUc9PVA:dir1/dir2/
