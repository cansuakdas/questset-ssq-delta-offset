# GitHub'a yükleme — hazır komutlar

## En kolay yöntem: GitHub CLI

1. GitHub CLI kurulu değilse macOS Terminal'de:

```bash
brew install gh
```

2. Giriş yapın:

```bash
gh auth login
```

3. ZIP'i açın, klasöre girin ve şu komutları çalıştırın:

```bash
cd questset-ssq-delta-offset
git init
git add .
git commit -m "Initial public Questset SSQ and delta-offset analysis"
git branch -M main
gh repo create questset-ssq-delta-offset --public --source=. --remote=origin --push
```

Repo adını değiştirmek için son komuttaki `questset-ssq-delta-offset` kısmını değiştirin.

## GitHub web sitesi + klasik Git yöntemi

1. GitHub'da **New repository** seçin.
2. Repo adını `questset-ssq-delta-offset` yazın ve **Public** seçin.
3. README/license/gitignore eklemeden boş repo oluşturun; bunlar pakette zaten var.
4. GitHub'ın verdiği kullanıcı adınıza göre aşağıdaki komutu düzenleyin:

```bash
cd questset-ssq-delta-offset
git init
git add .
git commit -m "Initial public Questset SSQ and delta-offset analysis"
git branch -M main
git remote add origin https://github.com/GITHUB_KULLANICI_ADINIZ/questset-ssq-delta-offset.git
git push -u origin main
```

## Yüklemeden önce kontrol

```bash
git status
find . -type f | sort
```

`data/` altında gerçek katılımcı CSV dosyaları veya `outputs/` altında büyük çıktı dosyaları görünmemelidir. `.gitignore` bunları dışarıda tutar.
