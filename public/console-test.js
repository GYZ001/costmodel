// ============================================
// 股票分析系统 - 浏览器控制台诊断脚本
// 使用方法：在浏览器控制台中粘贴并执行
// ============================================

(function() {
    console.log('%c🔍 股票分析系统诊断开始', 'font-size: 16px; font-weight: bold; color: #4CAF50;');

    // Test 1: Health check
    console.log('\n%c1️⃣ 健康检查', 'font-weight: bold;');
    fetch('/api/health')
        .then(res => {
            console.log(`HTTP状态: ${res.status}`);
            return res.json();
        })
        .then(data => {
            console.log('%c✓ 健康检查成功', 'color: green;', data);
            return testAnalyze();
        })
        .catch(err => {
            console.error('%c✗ 健康检查失败', 'color: red;', err);
        });

    async function testAnalyze() {
        console.log('\n%c2️⃣ 股票分析测试', 'font-weight: bold;');

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    stock_code: '600519',
                    stock_name: '',
                    market: 'A股',
                    period: '日线',
                    days: 30
                })
            });

            console.log(`HTTP状态: ${response.status}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('%c✓ 股票分析成功', 'color: green;');
            console.log('股票代码:', data.stock_code);
            console.log('股票名称:', data.stock_name);
            console.log('投资建议:', data.recommendation);
            console.log('趋势:', data.technical_analysis.trend);
            console.log('完整数据:', data);

            // Test 3: Kline data
            console.log('\n%c3️⃣ K线数据测试', 'font-weight: bold;');
            await testKline();

        } catch (error) {
            console.error('%c✗ 股票分析失败', 'color: red;', error);
        }
    }

    async function testKline() {
        try {
            const response = await fetch('/api/kline?code=600519&days=30');
            console.log(`HTTP状态: ${response.status}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('%c✓ K线数据获取成功', 'color: green;');
            console.log('数据条数:', data.data.length);
            console.log('最新收盘价:', data.indicators.latest_close);
            console.log('MA5:', data.indicators.ma5);
            console.log('前3条数据:', data.data.slice(0, 3));

            // Test 4: News data
            console.log('\n%c4️⃣ 新闻数据测试', 'font-weight: bold;');
            await testNews();

        } catch (error) {
            console.error('%c✗ K线数据获取失败', 'color: red;', error);
        }
    }

    async function testNews() {
        try {
            const response = await fetch('/api/news?code=600519&name=%E8%B4%99%E5%B7%9E%E8%8C%85%E5%8F%91&days=7');
            console.log(`HTTP状态: ${response.status}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('%c✓ 新闻数据获取成功', 'color: green;');
            console.log('新闻条数:', data.data.length);
            console.log('情绪分析:', data.sentiment);

            console.log('\n%c🎉 所有测试完成！', 'font-size: 16px; font-weight: bold; color: #4CAF50;');
            console.log('%c如果看到这条消息，说明 API 调用都正常。', 'color: #666;');
            console.log('%c问题可能在前端代码的数据处理部分。', 'color: #666;');

        } catch (error) {
            console.error('%c✗ 新闻数据获取失败', 'color: red;', error);
        }
    }
})();
