from decimal import Decimal

# Ongkos kirim flat per toko (satu Order per seller).
SHIPPING_FEE_PER_STORE = Decimal("15000")

STATUS_DIPROSES = "diproses"
STATUS_DIKIRIM = "dikirim"
STATUS_SELESAI = "selesai"
STATUS_DIBATALKAN = "dibatalkan"

STATUS_CHOICES = [
    (STATUS_DIPROSES, "Diproses"),
    (STATUS_DIKIRIM, "Dikirim"),
    (STATUS_SELESAI, "Selesai"),
    (STATUS_DIBATALKAN, "Dibatalkan"),
]

PAYMENT_CHOICES = [
    ("transfer", "Transfer bank"),
    ("ewallet", "E-wallet"),
    ("cod", "Bayar di tempat (COD)"),
]
