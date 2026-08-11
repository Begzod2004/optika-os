# Optika OS

Optika do'koni uchun CRM, POS, buyurtma va ombor boshqaruv tizimi.

## Ishga tushirish

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs

## Lokal demo

Ikki terminal oching:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm.cmd install
npm.cmd run dev -- -H 127.0.0.1
```

So'ng `http://localhost:3000` ni oching. Demo administratori: `admin` / `admin123`.

Productionga chiqarishdan oldin `backend/.env.example` dan `.env` yarating va `JWT_SECRET`ni tasodifiy, maxfiy qiymatga almashtiring.

Telegram bot mijozlar uchun ishlaydi. Sotuvchi mijoz kartasidan shaxsiy Telegram havolasini yaratadi va Telegram orqali yuboradi; mijoz havolani bossa profil avtomatik bog'lanadi. So'ng `/buyurtmalar` bilan faol buyurtmalarini ko'radi. Buyurtma `Tayyor` holatiga o'tganda bog'langan mijozga avtomatik xabar yuboriladi. Tokenni faqat `backend/.env` ichida saqlang va hech qachon chat yoki gitga yubormang.

Lokal frontend development:

```bash
cd frontend
npm install
npm run dev
```

## Hozirgi holat

CRM, retseptlar, POS, sotuvlar/qaytarish, buyurtmalar, ombor ledgeri, supplier/kirim,
kassa smenasi, xarajatlar, qarzdorlik to'lovlari, audit log va moliyaviy hisobotlar.

Shuningdek PWA qobig'i, tizim foydalanuvchilari uchun ichki ogohlantirishlar, servis/ta'mirlash, xodimlar rollari va retsept bo'yicha aqlli optik tavsiyalar mavjud.
