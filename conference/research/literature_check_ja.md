# 文献の実在の確かめ（Claude、2026-11-23）

ChatGPT の調査（2 回分）に出てきた文献を、Crossref の API（`api.crossref.org`）で確かめた。
- DOI があるものは、その DOI で確かめた。DOI がない・違うものは、題名で検索した。
- arXiv・出版社のページは、このクラウドの環境からは開けなかった（ネットワークの制限）。なので、**要旨の引用文が原文と合うかは確かめていない**。

## 実在を確かめた（題名・第 1 著者・年・掲載先が一致）
| 文献 | DOI | 備考 |
|---|---|---|
| Fankhauser 2018, Probabilistic Terrain Mapping…, RA-L | 10.1109/LRA.2018.2849506 | |
| Fankhauser 2014, Robot-Centric Elevation Mapping…, CLAWAR | 10.1142/9789814623353_0051 | |
| Triebel 2006, Multi-Level Surface Maps…, IROS | 10.1109/IROS.2006.282632 | |
| Lu 2014, Layered costmaps…, IROS | 10.1109/IROS.2014.6942636 | |
| Lee 2022, Patchwork++, IROS | 10.1109/IROS47612.2022.9981561 | 題名で検索して一致（DOI の直接の照会は失敗） |
| Paigwar 2020, GndNet, IROS | 10.1109/IROS45743.2020.9340979 | |
| Blackmore 2011, Chance-Constrained Optimal Path Planning…, T-RO | 10.1109/TRO.2011.2161160 | |
| Xie 2023, Real-Time Elevation Mapping with Bayesian Ground Filling…, IROS | 10.1109/IROS55552.2023.10341662 | |
| Krüsi, Driving on Point Clouds…, JFR | 10.1002/rob.21700 | Crossref の年は 2016（オンライン版の年）。報告では 2017 |
| Fan 2021, STEP, RSS | 10.15607/RSS.2021.XVII.021 | |
| Meng 2023, TerrainNet, RSS | 10.15607/rss.2023.xix.103 | |
| Gasparino 2022, WayFAST, RA-L | 10.1109/LRA.2022.3193464 | |
| Xu, Hybrid Trajectory Optimization… Tracked Robots, RA-L | 10.1109/LRA.2023.3337593 | Crossref の年は 2024 |
| Fankhauser 2016, Collaborative navigation for flying and walking robots, IROS | 10.1109/IROS.2016.7759443 | |
| Garimella 2018, Robust Obstacle Avoidance using Tube NMPC, RSS | 10.15607/RSS.2018.XIV.055 | |
| Janson 2018, Safe Motion Planning in Unknown Environments…, RSS | 10.15607/rss.2018.xiv.061 | 題名で一致 |
| Kim 2022, LT-mapper, ICRA | 10.1109/icra46639.2022.9811916 | 題名で一致 |
| Liu 2023, Hybrid Map-Based Path Planning…, IROS | 10.1109/IROS55552.2023.10341666 | |
| Liu 2025, A Long-Term SLAM System… Dual-Layer Octree Change Detection, IEEE Sensors J. | 10.1109/JSEN.2025.3604515 | |
| Li 2024, ParkingE2E, IROS | 10.1109/IROS58592.2024.10801763 | |
| Leu 2022, Autonomous Vehicle Parking in Dynamic Environments…, ICRA | 10.1109/ICRA46639.2022.9812309 | |
| Li, Safe Motion Planning… Deep Learning-Enabled Environment Perception, T-IV | 10.1109/TIV.2023.3297735 | Crossref の年は 2024 |
| Borges 2022, A Survey on Terrain Traversability Analysis…, Field Robotics | 10.55417/fr.2022049 | |
| Jasour 2019, Risk Contours Map…, RSS | 10.15607/rss.2019.xv.056 | |
| Adu 2023, RADIUS, RSS | 10.15607/rss.2023.xix.083 | |
| Manchester 2017, DIRTREL, RSS | 10.15607/rss.2017.xiii.057 | |
| Sakayori 2024, slip rate-dependent traversability… sandy terrain, Frontiers in Robotics and AI | 10.3389/frobt.2024.1320261 | |
| Kahn, BADGR, RA-L | 10.1109/lra.2021.3057023 | 報告では arXiv 2020。RA-L 2021 にも出ている |
| He 2022, Diff-Net, ICRA | 10.1109/icra46639.2022.9811573 | 報告では arXiv 2021 |
| Theurkauf 2023, Chance-Constrained Motion Planning with Event-Triggered Estimation, ICRA | 10.1109/icra48891.2023.10160940 | 報告では arXiv 2022 |
| Zhao 2025, CurbNet, IEEE T-ITS | 10.1109/tits.2025.3540645 | 報告では arXiv 2024 |
| Trivedi 2025, Data-Driven Sampling Based Stochastic MPC for Skid-Steer…, ICRA | 10.1109/icra55743.2025.11127456 | |

## 実在するが、報告の書誌が違った
| 報告の書き方 | 実際（Crossref） |
|---|---|
| 「M. A. A. Cassie 系 reactive planning」T-RO 2023, 10.1109/TRO.2022.3228713 | 題名は合う。第 1 著者は Huang（「Cassie」はロボットの名前で、著者名ではない） |
| DRIVE Through the Unpredictability…, T-FR 2025（著者なし） | 第 1 著者 Samson。DOI 10.1109/TFR.2025.3580397 は一致 |

## arXiv だけで、ここでは確かめられなかった（Crossref に出ない）
- Shalev-Shwartz 2017, On a Formal Model of Safe and Scalable Self-driving Cars（arXiv 1708.06374）
- Lambert 2022, Trust, but Verify（arXiv 2212.07312）
- Wild 2024, ExelMap（arXiv 2409.10178）
- Massera 2020, Tube-based Guaranteed Cost MPC…（arXiv 2012.05334）
- Roth 2023, ViPlanner（arXiv 2310.00982。検索の失敗で未確認）
→ よく知られた文献もあるが、引用する前に arXiv のページで確かめる。

## 両方の報告が「見つからなかった」と書いたこと
- 「地形の誤判定が、障害物の安全の余白として偶然働き、誤判定を直すと余白が減る」ことを直接分析した論文。
- 「砂浜・漂着物の回収・装軌式・航空 LiDAR の事前の地図・走行中の更新」の組み合わせの論文。
（2 つの調査で見つからなかっただけで、ないとは言えない。修論では「調べた範囲では見当たらない」と書く。）

## Gemini の調査（2 回分）にだけ出てきた文献（Crossref で確かめた）
| 文献 | DOI | 結果 |
|---|---|---|
| Miki 2022, Elevation Mapping for Locomotion and Navigation using GPU, IROS | 10.1109/iros47612.2022.9981507 | 実在 |
| Inotsume 2020, Robust Path Planning for Slope Traversing Under Uncertainty in Slip Prediction, RA-L | 10.1109/LRA.2020.2975756 | 実在 |
| Frey 2023, Fast Traversability Estimation for Wild Visual Navigation, RSS | 10.15607/RSS.2023.XIX.054 | 実在 |
| Oleynikova 2017, Voxblox, IROS | 10.1109/IROS.2017.8202315 | 実在 |
| Macenski 2020, The Marathon 2: A Navigation System, IROS | 10.1109/iros45743.2020.9341207 | 実在 |
| Feng 2026, Safe and Fast Motion Planning for UGV on Unknown Uneven Terrain… CBF Constraints, Drones | 10.3390/drones10060440 | 実在（MDPI の雑誌。主要な場ではない） |
| Knuth 2021, Planning with Learned Dynamics…, RA-L | 10.1109/lra.2021.3068889 | 実在 |
| Pomerleau 2014, Long-term 3D map maintenance in dynamic environments, ICRA | 10.1109/icra.2014.6907397 | 実在 |
| Mentasti 2021, Two algorithms for vehicular obstacle detection in sparse pointcloud | 10.23919/aeitautomotive52815.2021.9662780 | 実在（AEIT Automotive 2021。報告では arXiv のみ） |
| Zhu 2019, Chance-constrained Collision Avoidance for MAVs in Dynamic Environments, RA-L | 10.1109/lra.2019.2893494 | 実在 |
| Takemura 2021, Traversability-based Trajectory Planning with Quasi-Dynamic Vehicle Model in Loose Soil, IROS | 10.1109/iros51168.2021.9635891 | 実在 |
| Ishigami 2007, Terramechanics-based model for steering maneuver… loose soil, JFR | 10.1002/rob.20187 | 実在 |
| Majumdar 2017, Funnel libraries…, IJRR | 10.1177/0278364917712421 | 実在 |
| Dixit 2024, STEP… DARPA SubT, Field Robotics | 10.55417/fr.2024006 | **Crossref で見つからない**（DOI が違う可能性。引用前に確かめる） |

Gemini の 2 回目は、要旨まで確かめられた文献だけを本文に挙げ、ほかを「未確認」に分けていた。そこに挙がった arXiv の番号（2606・2608・2610・2611 で始まるものなど）は、ここでは確かめていない。
「CMU の著者名なしの資料」「Jinno（年不明）」は書誌が不完全なので、使わない。

## 自己位置推定（GNSS なし・砂浜）のディープリサーチ（2026-11-26、利用者が貼ったレポート 1 本目、Claude が Crossref で確かめた）
- DOI のある 26 本は、すべて Crossref で実在を確かめた（題名が一致）。
- **筆頭著者の誤り**（レポートの書き方 → 本当の筆頭著者）：
  - 「Barsi 系, 2022」（10.1016/j.jag.2022.102767）→ **Zováthi**
  - 「Hara / Nakamura et al., 2023」（10.1186/s40648-023-00256-w）→ **Kondo**
  - 「Wong 系を踏襲した tracked vehicle 研究, 2010」（10.1016/j.jterra.2010.02.001）→ **Al-Milli**
- 年のずれ（オンライン公開と巻号の差で、問題なし）：Katwijk 2017/2018、Nourizadeh 2022/2023、Pavlov 2024/2023。
- DOI がなく確かめていないもの：COIN-LIO（ICRA 2024）、AdaLIO（arXiv 2304.12577）、X-ICP（arXiv 2211.16335）、Fisher Information Field（arXiv 2008.03324）、Pretto 2018（IROS ワークショップ）。
- **レポートの数値（ENWIDE・GEODE の誤差の表など）は確かめていない**。使うときは原著の表で確かめる。
- 特に使えそうなもの：
  - Hewitt 2017（Katwijk beach dataset）：本物の砂浜、VLP-16＋IMU＋RTK-GPS（正解）＋走る前の UAV の DEM（約 20cm の高さの精度）。今回の問題に一番近い公開データ。
  - Chen 2025（GEODE）・COIN-LIO の ENWIDE：特徴の少ない環境での LIO のずれ。
  - Kondo 2023・Chai 2024（LF-3PM）・Kim 2023・Zhang 2019：地図から前もって「位置の決まりやすさ」を出し、経路の計画に使う。071 の考え方の先行研究。
  - Giordano 2025：海岸での UAV 点群どうしの位置合わせ（特徴のない面の限界）。
