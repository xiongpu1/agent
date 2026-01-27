#!/bin/bash
# 监控钉盘文件处理进度

echo "========================================"
echo "钉盘文件处理进度监控"
echo "========================================"
echo ""

# 检查进程是否在运行
PID=$(pgrep -f "run_dingtalk_pipeline.py")
if [ -z "$PID" ]; then
    echo "❌ 处理进程未运行"
    echo ""
    echo "查看最后的日志:"
    tail -20 pipeline_full.log
    exit 1
fi

echo "✅ 处理进程正在运行 (PID: $PID)"
echo ""

# 显示处理结果统计
if [ -f "data_storage/dingtalk_processing_results.json" ]; then
    echo "📊 当前统计:"
    python3 -c "
import json
data = json.load(open('data_storage/dingtalk_processing_results.json'))
print(f'  总计: {data[\"total\"]}')
print(f'  成功: {data[\"success\"]}')
print(f'  失败: {data[\"failed\"]}')
print(f'  跳过: {data[\"skipped\"]}')
print(f'  最后更新: {data.get(\"last_update\", \"未知\")}')
"
    echo ""
fi

# 显示进度信息
if [ -f "data_storage/dingtalk_progress.json" ]; then
    echo "📈 处理进度:"
    python3 -c "
import json
data = json.load(open('data_storage/dingtalk_progress.json'))
total = data.get('total_files', 0)
processed = data.get('processed_files', 0)
current_batch = data.get('current_batch', 0)
total_batches = data.get('total_batches', 0)
if total > 0:
    percent = (processed / total) * 100
    print(f'  已处理: {processed}/{total} ({percent:.1f}%)')
    print(f'  当前批次: {current_batch}/{total_batches}')
    print(f'  最后更新: {data.get(\"last_update\", \"未知\")}')
"
    echo ""
fi

# 显示最新日志
echo "📝 最新日志 (最后 10 行):"
tail -10 pipeline_full.log | grep -v "^$"
echo ""

echo "========================================"
echo "提示:"
echo "  - 查看完整日志: tail -f pipeline_full.log"
echo "  - 停止处理: kill $PID"
echo "  - 重新运行监控: bash monitor_progress.sh"
echo "========================================"
