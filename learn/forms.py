from django import forms
from .models import BangCap, MotivationalQuote, Course, TrainingProviderLink

class BangCapForm(forms.ModelForm):
    AUTO_COMMENT_RULES = [
        (
            ("ロボット", "robot", "産業用ロボット"),
            "ロボット関連資格。安全基準を遵守し、ティーチング・段取り・異常時対応を現場で実践できることを確認。",
        ),
        (
            ("玉掛け", "tamakake", "つり上げ"),
            "玉掛け関連資格。合図・荷重確認・吊り具点検を徹底し、安全第一で作業できることを確認。",
        ),
        (
            ("フォークリフト", "forklift"),
            "フォークリフト関連資格。運搬ルール・死角確認・接触防止を含む安全運転スキルを確認。",
        ),
        (
            ("クレーン", "crane"),
            "クレーン関連資格。定格荷重・作業半径・合図連携を理解し、安全作業を実施できることを確認。",
        ),
        (
            ("電気", "electrical"),
            "電気系資格。感電・短絡リスクを踏まえた点検手順と保全対応スキルを確認。",
        ),
        (
            ("qc", "品質", "検査"),
            "品質管理関連資格。標準作業・記録・異常検知を通じて品質保証に貢献できることを確認。",
        ),
    ]

    loai_bang = forms.CharField(
        label='資格の種類',
        max_length=64,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: QC検定 / 社内認定 / 安全教育修了証'}),
    )

    class Meta:
        model = BangCap
        fields = ['loai_bang', 'cap_do', 'file', 'ngay_cap', 'ghi_chu']
        labels = {
            'loai_bang': '資格の種類',
            'cap_do': '級',
            'file': '証明書ファイル（PDFまたは画像）',
            'ngay_cap': '発行日',
            'ghi_chu': '備考',
        }
        widgets = {
            'file': forms.FileInput(attrs={'accept': '.pdf,image/*'}),
            'ngay_cap': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'cap_do': forms.Select(attrs={'class': 'form-select'}),
            'ghi_chu': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        defaults = list(BangCap.DEFAULT_LOAI_BANG)
        existing = list(
            BangCap.objects.exclude(loai_bang__exact="")
            .order_by()
            .values_list('loai_bang', flat=True)
            .distinct()
        )
        # Dùng cho datalist ở template (gợi ý, vẫn cho nhập tự do)
        self.loai_bang_suggestions = sorted(set(defaults + existing))

    def _build_auto_comment(self, loai_bang: str, cap_do: str) -> str:
        loai = (loai_bang or "").strip()
        level = (cap_do or "").strip()
        lower = loai.lower()

        for keywords, message in self.AUTO_COMMENT_RULES:
            if any(k.lower() in lower for k in keywords):
                return f"{message}（分類: {loai} / 級: {level or '-'}）"

        if loai:
            return f"{loai}の資格を取得。業務適用範囲と安全・品質要求を理解し、現場で活用できることを確認。"
        return ""

    def clean(self):
        cleaned = super().clean()
        loai_bang = (cleaned.get("loai_bang") or "").strip()
        ghi_chu = (cleaned.get("ghi_chu") or "").strip()
        cap_do = cleaned.get("cap_do") or ""

        cleaned["loai_bang"] = loai_bang
        if not ghi_chu and loai_bang:
            cleaned["ghi_chu"] = self._build_auto_comment(loai_bang, cap_do)
        return cleaned


class MotivationalQuoteForm(forms.ModelForm):
    class Meta:
        model = MotivationalQuote
        fields = ['text', 'author']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CourseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # description đã ẩn khỏi UI nên không bắt buộc để tránh lỗi submit
        required_fields = {
            'title',
            'external_url',
            'start_date',
            'end_date',
            'price',
            'duration',
            'location',
            'target',
        }
        for name, field in self.fields.items():
            field.required = name in required_fields

    class Meta:
        model = Course
        fields = [
            'title', 'external_url', 'start_date', 'end_date', 'price', 'duration',
            'material', 'location', 'target', 'is_active'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class TrainingProviderLinkForm(forms.ModelForm):
    class Meta:
        model = TrainingProviderLink
        fields = ['name', 'url', 'category', 'icon_class', 'is_active']
        labels = {
            'name': '会社・団体名',
            'url': 'URL',
            'category': 'カテゴリ',
            'icon_class': 'アイコン（任意）',
            'is_active': '表示',
            'title': '研修・講習名',
            'external_url': '外部リンク',
            'start_date': '開始日',
            'end_date': '終了日',
            'price': '受講料',
            'duration': '研修期間（時間）',
            'material': '資料アップロード',
            'location': '場所',
            'target': '対象',
            'description': '参加の理由',
            
        }
        error_messages = {
            'title': {
                'required': '研修・講習名は必須項目です。',
                'max_length': '研修・講習名が長すぎます。',
            },
            'external_url': {
                'required': '外部リンクは必須項目です。',
                'invalid': '有効なURLを入力してください。',
            },
            'start_date': {
                'required': '開始日は必須項目です。',
                'invalid': '有効な日付を入力してください。',
            },
            'end_date': {
                'required': '終了日は必須項目です。',
                'invalid': '有効な日付を入力してください。',
            },
            'price': {
                'required': '受講料は必須項目です。',
                'invalid': '数字で入力してください。',
            },
            'duration': {
                'required': '研修期間は必須項目です。',
                'invalid': '数字で入力してください。',
            },
            'material': {
                'invalid': 'PDFまたは画像ファイルをアップロードしてください。',
            },
            'location': {
                'required': '場所は必須項目です。',
            },
            'target': {
                'required': '対象は必須項目です。',
            },
            'description': {
                'required': '参加の理由は必須項目です。',
            },
            'is_active': {
                'invalid': '有効な値を選択してください。',
            },
        }
