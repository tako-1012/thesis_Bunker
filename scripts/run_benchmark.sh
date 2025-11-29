#!/bin/bash
################################################################################
# ベンチマーク実験自動実行スクリプト
# 
# 使用方法:
#   ./run_benchmark.sh                    # デフォルトシナリオで実行
#   ./run_benchmark.sh --full             # 全シナリオで実行
#   ./run_benchmark.sh --quick            # クイックテスト（3シナリオ）
#   ./run_benchmark.sh --visualize-only   # 可視化のみ
################################################################################

set -e  # エラーで停止

# スクリプトのディレクトリ
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="/home/hayashi/thesis_work"

# パス設定
BENCHMARK_SCRIPT="${PROJECT_ROOT}/scripts/benchmark_path_planners.py"
VISUALIZE_SCRIPT="${PROJECT_ROOT}/scripts/visualize_benchmark_results.py"
SCENARIOS_FILE="${PROJECT_ROOT}/scenarios/benchmark_scenarios.json"
RESULTS_DIR="${PROJECT_ROOT}/results"
FIGURES_DIR="${PROJECT_ROOT}/figures"

# ディレクトリ作成
mkdir -p "${RESULTS_DIR}"
mkdir -p "${FIGURES_DIR}"

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ヘッダー表示
print_header() {
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}======================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# 引数解析
MODE="default"
VISUALIZE_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --full)
            MODE="full"
            shift
            ;;
        --quick)
            MODE="quick"
            shift
            ;;
        --visualize-only)
            VISUALIZE_ONLY=true
            shift
            ;;
        --help)
            echo "使用方法:"
            echo "  ./run_benchmark.sh                    # デフォルトシナリオで実行"
            echo "  ./run_benchmark.sh --full             # 全シナリオで実行"
            echo "  ./run_benchmark.sh --quick            # クイックテスト"
            echo "  ./run_benchmark.sh --visualize-only   # 可視化のみ"
            exit 0
            ;;
        *)
            echo "不明なオプション: $1"
            echo "使用方法: ./run_benchmark.sh [--full|--quick|--visualize-only|--help]"
            exit 1
            ;;
    esac
done

# タイムスタンプ
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULT_FILE="${RESULTS_DIR}/benchmark_results_${TIMESTAMP}.json"

# 可視化のみモード
if [ "$VISUALIZE_ONLY" = true ]; then
    print_header "ベンチマーク結果可視化モード"
    
    # 最新の結果ファイルを探す
    LATEST_RESULT=$(ls -t "${RESULTS_DIR}"/benchmark_results_*.json 2>/dev/null | head -n 1)
    
    if [ -z "$LATEST_RESULT" ]; then
        print_error "結果ファイルが見つかりません: ${RESULTS_DIR}"
        exit 1
    fi
    
    print_info "結果ファイル: ${LATEST_RESULT}"
    
    print_header "可視化実行中..."
    python3 "${VISUALIZE_SCRIPT}" "${LATEST_RESULT}" --output "${FIGURES_DIR}"
    
    print_success "可視化完了！"
    print_info "出力先: ${FIGURES_DIR}"
    
    exit 0
fi

# メインの実行フロー
print_header "ベンチマーク実験自動実行システム"

echo ""
print_info "モード: ${MODE}"
print_info "タイムスタンプ: ${TIMESTAMP}"
print_info "結果出力: ${RESULT_FILE}"
echo ""

# Python環境チェック
print_info "Python環境を確認中..."
if ! command -v python3 &> /dev/null; then
    print_error "Python3が見つかりません"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
print_success "Python環境: ${PYTHON_VERSION}"

# 必要なPythonパッケージのチェック
print_info "必要なパッケージを確認中..."
REQUIRED_PACKAGES=("numpy" "matplotlib" "seaborn")
MISSING_PACKAGES=()

for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if ! python3 -c "import ${pkg}" 2>/dev/null; then
        MISSING_PACKAGES+=("${pkg}")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    print_error "以下のパッケージが不足しています: ${MISSING_PACKAGES[*]}"
    print_info "インストールするには: pip3 install ${MISSING_PACKAGES[*]}"
    exit 1
fi

print_success "すべてのパッケージが揃っています"

# ベンチマーク実行
print_header "ベンチマーク実行中..."

case $MODE in
    quick)
        print_info "クイックテストモード（デフォルトシナリオのみ）"
        python3 "${BENCHMARK_SCRIPT}" --output "${RESULTS_DIR}" --voxel-size 0.1
        ;;
    full)
        print_info "フルテストモード（全シナリオ）"
        if [ ! -f "${SCENARIOS_FILE}" ]; then
            print_error "シナリオファイルが見つかりません: ${SCENARIOS_FILE}"
            exit 1
        fi
        python3 "${BENCHMARK_SCRIPT}" --scenario "${SCENARIOS_FILE}" --output "${RESULTS_DIR}" --voxel-size 0.1
        ;;
    default)
        print_info "デフォルトモード"
        python3 "${BENCHMARK_SCRIPT}" --output "${RESULTS_DIR}" --voxel-size 0.1
        ;;
esac

# ベンチマーク結果チェック
if [ $? -eq 0 ]; then
    print_success "ベンチマーク実行完了"
else
    print_error "ベンチマーク実行中にエラーが発生しました"
    exit 1
fi

# 最新の結果ファイルを取得
LATEST_RESULT=$(ls -t "${RESULTS_DIR}"/benchmark_results_*.json 2>/dev/null | head -n 1)

if [ -z "$LATEST_RESULT" ]; then
    print_error "結果ファイルが生成されませんでした"
    exit 1
fi

print_info "結果ファイル: ${LATEST_RESULT}"

# 可視化実行
print_header "結果可視化中..."

python3 "${VISUALIZE_SCRIPT}" "${LATEST_RESULT}" --output "${FIGURES_DIR}"

if [ $? -eq 0 ]; then
    print_success "可視化完了"
else
    print_error "可視化中にエラーが発生しました"
    exit 1
fi

# 完了メッセージ
print_header "実験完了！"

echo ""
print_success "すべての処理が正常に完了しました"
echo ""
print_info "生成されたファイル:"
echo "  - 結果データ: ${LATEST_RESULT}"
echo "  - グラフ: ${FIGURES_DIR}/"
echo ""

# グラフファイル一覧表示
if [ -d "${FIGURES_DIR}" ]; then
    echo "生成されたグラフ:"
    ls -lh "${FIGURES_DIR}"/*.png 2>/dev/null | awk '{print "  - " $9}' || echo "  (なし)"
fi

echo ""
print_info "結果を確認するには:"
echo "  cat ${LATEST_RESULT} | python3 -m json.tool"
echo ""
print_info "グラフを開くには:"
echo "  xdg-open ${FIGURES_DIR}/"
echo ""

print_header "実験終了"
