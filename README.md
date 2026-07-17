# Questset SSQ & Delta-Offset Analysis

Bu depo, açık **Questset** VR veri setindeki trafik, hareket ve SSQ dosyalarını kullanarak tekrar üretilebilir bir başlangıç analizi sunar. Veri setinin kendisi repoya eklenmez; yalnızca analiz kodu paylaşılır.

## Bu sürüm ne ekliyor?

Orijinal Questset trafik işleme yaklaşımını temel alır: downlink paketlerinden 27 bayt USBPcap başlığı çıkarılır, 5 kB üzerindeki paketler seçilir, 5 ms'den kısa paket aralıkları aynı video karesinde kümelenir ve 72 FPS zaman çizelgesindeki eksik kareler sıfır boyutlu kare olarak eklenir.

Bu repodaki ek analizler:

1. **Standart SSQ skorları:** Nausea, Oculomotor, Disorientation ve Total skorları Kennedy SSQ ağırlıklarıyla hesaplanır.
2. **Oturuma özgü SSQ değişimi (`ssq_delta`):** İlgili oyundan hemen önceki ve hemen sonraki anket skorlarının farkıdır. Questset sıralama bilgisi otomatik yorumlanır (`order1`: slow önce, `order2`: fast önce).
3. **Trafik–hareket delta offset:** Her ham video karesi en yakın hareket örneğiyle eşleştirilir. `delta_offset_ms = motion_time - frame_time`. Pozitif değer, hareket örneğinin kare zamanından sonra geldiğini gösterir. Mutlak offset ve 5 ms toleransını aşan hizasızlık oranı da raporlanır.
4. **Kare risk bayrakları:** skipped frame, long gap, yüksek IFI değişimi veya hareket hizasızlığı olan kareler işaretlenir.

> Not: `mean_packet_interval_ms` gerçek uçtan uca ağ gecikmesi değildir; seçilmiş DL paketleri arasındaki ortalama zaman aralığıdır.

## Veri seti

Questset, 70 katılımcıdan 40 saatin üzerinde VR trafik, HMD/controller hareketi ve SSQ verisi içerir. Resmî veri sayfası:

- Dataset: https://researchdata.cab.unipd.it/1179/
- Orijinal API: https://github.com/signetlabdei/questset
- Makale DOI: https://doi.org/10.1145/3625468.3652187

Veri setini indirip örneğin şu yapıda tutun:

```text
data/
├── Complete data/
│   ├── SSQ.csv
│   └── group1_order1_user0/
│       ├── group1_order1_user0_fast_traffic.csv
│       ├── group1_order1_user0_fast_movement.csv
│       ├── group1_order1_user0_slow_traffic.csv
│       └── group1_order1_user0_slow_movement.csv
└── Incomplete data/
```

## Kurulum

```bash
cd questset-ssq-delta-offset
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .
```

## Çalıştırma

Complete data için:

```bash
questset-analyze \
  --data-root "data/Complete data" \
  --output-dir "outputs/complete"
```

Incomplete data için:

```bash
questset-analyze \
  --data-root "data/Incomplete data" \
  --output-dir "outputs/incomplete"
```

Kare bazlı büyük CSV'leri üretmeden yalnızca özet almak için:

```bash
questset-analyze --data-root "data/Complete data" --no-frame-files
```

## Çıktılar

`session_summary.csv` her kullanıcı ve oyun koşulu için şunları içerir:

- bitrate, paket aralığı ve jitter özeti
- ortalama HMD hareket şiddeti
- skipped/risk frame sayıları
- ortalama, %95 ve maksimum mutlak delta offset
- motion misalignment oranı
- `ssq_pre`, `ssq_post`, `ssq_delta`

Her oturumun `*_frames_with_flags.csv` dosyasında `delta_offset_ms`, `abs_delta_offset_ms`, `skipped_frame`, `long_gap`, `high_var`, `motion_misaligned` ve `risk_flag` bulunur.

## Yöntemle ilgili önemli varsayımlar

- Trafik ve hareket zamanları her dosyanın ilk örneğine göre sıfırlanır. Bu nedenle delta offset, ortak mutlak saat yerine oturum içi göreli hizalamayı ölçer.
- En yakın hareket örneği eşleştirmesi kullanılır; nedensel gecikme ölçümü değildir.
- 5 ms packet clustering ve 72 FPS değerleri Questset'in yayımlanan işleme yaklaşımından gelir.
- 5 ms alignment toleransı ve risk eşikleri araştırma amaçlı başlangıç değerleridir; sonuç raporlanmadan önce duyarlılık analizi yapılmalıdır.

## Atıf

Bu kodu kullanırken Questset makalesini ve veri setini atıflayın:

```bibtex
@inproceedings{baldoni2024questset,
  title={Questset: A VR Dataset for Network and Quality of Experience Studies},
  author={Baldoni, Sara and Battisti, Federica and Chiariotti, Federico and others},
  booktitle={ACM Multimedia Systems Conference},
  year={2024},
  doi={10.1145/3625468.3652187}
}
```

## Lisans

Bu repodaki kod MIT lisansı altındadır. Questset verisinin ve orijinal kodun kendi lisans/atıf koşulları ayrıca geçerlidir. Veri dosyalarını bu repoya yüklemeyin.
