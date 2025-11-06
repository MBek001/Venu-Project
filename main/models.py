# myapp/models.py
from django.db import models


class Category(models.Model):
    """
    Mahsulot kategoriyalari modeli
    FastAPI dan olingan ma'lumotlar saqlanadi
    """
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255, db_index=True)  # Tez qidirish uchun index
    slug = models.SlugField(max_length=255, blank=True, null=True)
    parent_id = models.BigIntegerField(blank=True, null=True, db_index=True)

    class Meta:
        db_table = 'categories'
        verbose_name = 'Kategoriya'
        verbose_name_plural = 'Kategoriyalar'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_products_count(self):
        """Kategoriyaga tegishli mahsulotlar soni"""
        return Product.objects.filter(category_id=self.id).count()


class Product(models.Model):
    """
    Mahsulotlar modeli
    FastAPI dan olingan ma'lumotlar saqlanadi
    """
    id = models.BigIntegerField(primary_key=True)
    user_id = models.BigIntegerField(blank=True, null=True)
    added_by = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255, db_index=True)  # Tez qidirish uchun index
    code = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    slug = models.SlugField(max_length=255, blank=True, null=True)
    category_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    discount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    discount_type = models.CharField(max_length=50, blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    images = models.TextField(blank=True, null=True)
    colors = models.TextField(blank=True, null=True)
    choice_options = models.TextField(blank=True, null=True)
    variation = models.TextField(blank=True, null=True)
    current_stock = models.IntegerField(blank=True, null=True, default=0)
    product_type = models.CharField(max_length=50, blank=True, null=True)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    brand_id = models.BigIntegerField(blank=True, null=True, db_index=True)

    class Meta:
        db_table = 'products'
        verbose_name = 'Mahsulot'
        verbose_name_plural = 'Mahsulotlar'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name', 'category_id']),
            models.Index(fields=['unit_price']),
        ]

    def __str__(self):
        return self.name

    def get_category(self):
        """Mahsulot kategoriyasini qaytaradi"""
        try:
            return Category.objects.get(id=self.category_id)
        except Category.DoesNotExist:
            return None

    def get_price_display(self):
        """Narxni formatlangan holda qaytaradi"""
        if self.unit_price:
            return f"{self.unit_price:,.0f} so'm"
        return "Narx belgilanmagan"

    def is_in_stock(self):
        """Mahsulot omborda bormi?"""
        return self.current_stock and self.current_stock > 0