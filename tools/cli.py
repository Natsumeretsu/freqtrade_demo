"""命令行工具

提供便捷的命令行接口。

创建日期: 2026-01-17
"""
import click
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / '03_integration'))


@click.group()
def cli():
    """Trading System CLI 工具"""
    pass


@cli.command()
@click.option('--path', default='03_integration/trading_system/infrastructure', help='分析路径')
def check_types(path):
    """检查类型注解覆盖率"""
    from type_annotation_tool import analyze_directory
    
    directory = Path(path)
    results = analyze_directory(directory)
    
    total_funcs = results['total_functions']
    annotated_funcs = results['annotated_functions']
    func_coverage = (annotated_funcs / total_funcs * 100) if total_funcs > 0 else 0
    
    click.echo(f"函数覆盖率: {func_coverage:.2f}%")


@cli.command()
def monitor():
    """启动性能监控"""
    from trading_system.infrastructure.monitoring import PerformanceMonitor
    
    monitor = PerformanceMonitor(interval=1.0)
    monitor.start()
    
    click.echo("性能监控已启动，按 Ctrl+C 停止")
    
    try:
        import time
        while True:
            time.sleep(5)
            click.echo(monitor.get_report())
    except KeyboardInterrupt:
        monitor.stop()
        click.echo("监控已停止")


@cli.command()
@click.argument('output', default='reports/performance_report.txt')
def benchmark(output):
    """运行性能基准测试"""
    click.echo("运行性能基准测试...")
    
    import subprocess
    result = subprocess.run(
        ['python', 'tests/performance_benchmark.py'],
        capture_output=True,
        text=True
    )
    
    with open(output, 'w', encoding='utf-8') as f:
        f.write(result.stdout)
    
    click.echo(f"报告已保存到: {output}")


if __name__ == '__main__':
    cli()
