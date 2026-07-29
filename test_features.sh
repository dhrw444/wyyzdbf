#!/bin/bash

echo "=== 测试网易云音乐API功能 ==="
echo ""

echo "1. 测试首页访问..."
curl -s http://localhost:8000/ | grep -q "<title>" && echo "✅ 首页访问正常" || echo "❌ 首页访问失败"
echo ""

echo "2. 测试搜索API..."
curl -s -X POST http://localhost:8000/api/search -H "Content-Type: application/json" -d '{"keyword":"周杰伦"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ 搜索API正常' if d.get('success') else '❌ 搜索API失败')"
echo ""

echo "3. 测试播放API（需要登录）..."
curl -s -X POST http://localhost:8000/api/play -H "Content-Type: application/json" -d '{"mode":"mix","count":3}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ 播放API正常' if d.get('success') else '❌ 播放API失败')"
echo ""

echo "4. 测试API调试器..."
curl -s http://localhost:8000/api/api-debugger | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ API调试器正常' if d.get('success') else '❌ API调试器失败')"
echo ""

echo "5. 检查前端文件完整性..."
[ -f /workspace/index.html ] && echo "✅ index.html 存在" || echo "❌ index.html 不存在"
[ -f /workspace/app_combined.js ] && echo "✅ app_combined.js 存在" || echo "❌ app_combined.js 不存在"
[ -f /workspace/server.js ] && echo "✅ server.js 存在" || echo "❌ server.js 不存在"
echo ""

echo "=== 测试完成 ==="
