# Thailand General Election Ballot 2026

เว็บ Flask แบบเรียบง่ายสำหรับดูข้อมูลเปรียบเทียบจำนวนบัตรเลือกตั้งจากผลนับ 94% และ 100%

## แหล่งข้อมูล

ต้องดาวน์โหลดไฟล์ข้อมูลด้วยตนเองจาก [iLaw](https://www.facebook.com/iLawClub/posts/pfbid08jrF8X5vazkz1ykpdhSH72DCRNRp1eQC9r78VSSDRSgyWAeyAoHCV26FhXjsX4pPl) ก่อนใช้งาน

หลังดาวน์โหลดแล้ว ให้วางไฟล์ Excel ไว้ที่:

```text
data/ตารางคะแนนผลการเลือกตั้ง 2569.xlsx
```

ไฟล์ `data/` ไม่ได้ถูกเก็บใน git เพราะเป็นข้อมูลต้นทางและฐานข้อมูลที่สร้างขึ้นภายหลัง

## ติดตั้ง dependencies

ติดตั้ง Python packages จาก `requirements.txt`

```bash
python3 -m pip install -r requirements.txt
```

ถ้าเครื่องใช้ Python คนละตัวกับที่ติดตั้ง package ไว้ ให้ใช้ Python ตัวเดียวกันตอนรันคำสั่งถัดไป

## สร้างฐานข้อมูล

สร้างไฟล์ SQLite จาก schema:

```bash
python3 create_db.py
```

คำสั่งนี้จะสร้างฐานข้อมูลที่:

```text
data/ballot_2569.sqlite
```

จากนั้น import ข้อมูลจากไฟล์ Excel:

```bash
python3 import.py
```

## รันเว็บเซิร์ฟเวอร์

รัน Flask dev server:

```bash
python3 -m flask --app app run --debug
```

จากนั้นเปิดเว็บที่:

```text
http://127.0.0.1:5000
```

## หน้าเว็บหลัก

- `/` แสดงภาพรวมเปรียบเทียบจำนวนบัตร 94% กับ 100%
- `/negative` แสดงเฉพาะเขตที่มีอย่างน้อยหนึ่งช่องที่จำนวน 100% น้อยกว่า 94%
- `/province/<province_id>` แสดงรายละเอียดรายจังหวัด
- `/district/<constituency_id>` แสดงรายละเอียดรายเขตและผลคะแนนผู้สมัคร

## รันด้วย Docker

Docker image จะรวม `data/ballot_2569.sqlite` แต่ไม่รวมไฟล์ Excel ใน `data/`

ดึง public image แล้วรัน:

```bash
docker pull wittawasw/thailand-ballot-2026:latest
docker run --rm -p 5000:5000 wittawasw/thailand-ballot-2026:latest
```

เปิดเว็บที่:

```text
http://127.0.0.1:5000
```

สร้าง image เอง:

```bash
docker build -t thailand-ballot-2026 .
docker run --rm -p 5000:5000 thailand-ballot-2026
```
