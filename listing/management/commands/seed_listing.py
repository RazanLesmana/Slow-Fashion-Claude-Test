from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from listing.models import Product, ProductImage

# (seller, nama, brand, kategori, size, kondisi, harga, status)
PRODUCTS = [
    ("seller1", "Linen blazer krem", "Uniqlo", "outerwear", "M", "like_new", 85000, "active"),
    ("seller1", "Trench coat beige", "Zara", "outerwear", "M", "good", 180000, "active"),
    ("seller1", "Cardigan rajut abu", "Uniqlo", "atasan", "L", "good", 70000, "sold"),
    ("seller1", "Blazer hitam", "Zara", "outerwear", "M", "like_new", 90000, "active"),
    ("seller1", "Kemeja oversized putih", "Cotton On", "atasan", "M", "like_new", 55000, "active"),
    ("seller1", "Wool coat charcoal", "Mango", "outerwear", "M", "new", 220000, "sold"),
    ("seller1", "Overshirt flanel", "Cotton On", "atasan", "M", "good", 65000, "active"),
    ("seller1", "Parka olive", "H&M", "outerwear", "L", "good", 150000, "active"),
    ("seller1", "Midi dress motif bunga", "Mango", "dress", "S", "new", 150000, "active"),
    ("seller2", "Ribbed knit top hitam", "Zara", "atasan", "S", "good", 45000, "active"),
    ("seller2", "Wide leg trousers", "H&M", "bawahan", "L", "like_new", 60000, "active"),
    ("seller2", "501 jeans light wash", "Levi's", "bawahan", "30", "good", 120000, "active"),
    ("seller2", "Chuck 70 hitam", "Converse", "sepatu", "EU 39", "good", 250000, "active"),
    ("seller2", "Denim jacket washed", "Levi's", "outerwear", "M", "good", 110000, "active"),
    ("seller2", "Puffer vest hitam", "Uniqlo", "outerwear", "M", "like_new", 95000, "active"),
    ("seller2", "Bomber jacket olive", "H&M", "outerwear", "M", "good", 130000, "active"),
    ("seller2", "Windbreaker navy", "Uniqlo", "outerwear", "M", "fair", 75000, "sold"),
    ("seller2", "Suede jacket coklat", "Pull&Bear", "outerwear", "M", "like_new", 120000, "active"),
]


# Produk yang diberi 3 foto supaya galeri dan thumbnail bisa dicoba.
GALLERY_PRODUCTS = {"Linen blazer krem", "Trench coat beige", "Chuck 70 hitam"}
GALLERY_LABELS = ["Tampak depan", "Tampak belakang", "Detail"]

# Warna hanya dari palet monokrom situs.
BG_COLORS = ["#D9D3C7", "#F2EEE6"]
INK = "#1A1A1A"
GRAY = "#6B6B6B"
IMAGE_SIZE = 800


def _wrap(draw, text, font, max_width):
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def placeholder_image(product, label, index):
    """Gambar placeholder monokrom berisi brand, nama produk, dan label foto."""
    image = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), BG_COLORS[(product.pk + index) % len(BG_COLORS)])
    draw = ImageDraw.Draw(image)
    draw.rectangle([24, 24, IMAGE_SIZE - 25, IMAGE_SIZE - 25], outline=INK, width=2)

    small = ImageFont.load_default(size=28)
    big = ImageFont.load_default(size=56)
    draw.text((56, 56), (product.brand or "LaPAKAIAN").upper(), font=small, fill=GRAY)

    lines = _wrap(draw, product.name.upper(), big, IMAGE_SIZE - 112)
    y = (IMAGE_SIZE - len(lines) * 70) // 2
    for line in lines:
        draw.text((56, y), line, font=big, fill=INK)
        y += 70

    draw.text((56, IMAGE_SIZE - 90), label.upper(), font=small, fill=GRAY)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def add_images(product):
    """Tambah foto placeholder kalau produk belum punya foto. Mengembalikan jumlah foto baru."""
    if product.images.exists():
        return 0
    labels = GALLERY_LABELS if product.name in GALLERY_PRODUCTS else ["Foto produk"]
    for index, label in enumerate(labels):
        content = ContentFile(placeholder_image(product, label, index))
        item = ProductImage(product=product, alt_text=f"{product.name} - {label.lower()}")
        item.image.save(f"seed-{product.pk}-{index + 1}.jpg", content, save=True)
    return len(labels)


def description_for(name, brand, size):
    return (
        f"{name} dari {brand}, size {size}. Sudah dicuci dan dicek sebelum dikirim, "
        "tidak ada noda atau sobek. Ukuran detail bisa dilihat di size chart."
    )


class Command(BaseCommand):
    help = (
        "Buat ±18 produk demo untuk seller1 dan seller2 beserta foto placeholder. "
        "Aman dijalankan berulang (produk yang sudah punya foto tidak ditambah lagi)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--no-images", action="store_true", help="Lewati pembuatan foto placeholder.")

    def handle(self, *args, **options):
        sellers = {u.username: u for u in User.objects.filter(username__in=["seller1", "seller2"])}
        missing = {"seller1", "seller2"} - set(sellers)
        if missing:
            self.stdout.write(self.style.WARNING(
                f"User {', '.join(sorted(missing))} belum ada. Jalankan `python manage.py seed_akun` dulu."
            ))
            return

        created_count = 0
        image_count = 0
        for seller, name, brand, category, size, condition, price, status in PRODUCTS:
            product, created = Product.objects.get_or_create(
                seller=sellers[seller],
                name=name,
                defaults={
                    "brand": brand,
                    "description": description_for(name, brand, size),
                    "category": category,
                    "size": size,
                    "condition": condition,
                    "price": Decimal(price),
                    "status": status,
                },
            )
            created_count += int(created)
            if not options["no_images"]:
                image_count += add_images(product)

        self.stdout.write(self.style.SUCCESS(
            f"seed_listing selesai: {created_count} produk baru, {len(PRODUCTS) - created_count} sudah ada, "
            f"{image_count} foto baru."
        ))
