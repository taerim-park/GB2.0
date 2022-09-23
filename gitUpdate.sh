rm -rf ../GB2.0
mkdir ../GB2.0
git clone https://github.com/ekyuho/GB2.0.git ../GB2.0
cp ../GB2.0/COPY.sh .
sh COPY.sh
pm2 restart all