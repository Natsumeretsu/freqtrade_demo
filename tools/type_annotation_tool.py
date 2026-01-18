"""类型注解增强工具

为现有代码添加类型注解，提升代码质量。

创建日期: 2026-01-17
"""
import ast
import sys
from pathlib import Path
from typing import List, Dict, Set


class TypeAnnotationAnalyzer(ast.NodeVisitor):
    """类型注解分析器"""

    def __init__(self):
        self.functions_without_types: List[str] = []
        self.classes_without_types: List[str] = []
        self.total_functions = 0
        self.total_classes = 0
        self.annotated_functions = 0
        self.annotated_classes = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """访问函数定义"""
        self.total_functions += 1

        # 检查返回类型注解
        has_return_annotation = node.returns is not None

        # 检查参数类型注解
        has_param_annotations = any(
            arg.annotation is not None
            for arg in node.args.args
        )

        if has_return_annotation or has_param_annotations:
            self.annotated_functions += 1
        else:
            self.functions_without_types.append(node.name)

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """访问类定义"""
        self.total_classes += 1

        # 检查类属性是否有类型注解
        has_annotations = False
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                has_annotations = True
                break

        if has_annotations:
            self.annotated_classes += 1
        else:
            self.classes_without_types.append(node.name)

        self.generic_visit(node)

    def get_coverage(self) -> Dict[str, float]:
        """获取类型注解覆盖率"""
        func_coverage = (
            self.annotated_functions / self.total_functions * 100
            if self.total_functions > 0 else 0
        )
        class_coverage = (
            self.annotated_classes / self.total_classes * 100
            if self.total_classes > 0 else 0
        )
        return {
            'function_coverage': func_coverage,
            'class_coverage': class_coverage,
            'total_coverage': (func_coverage + class_coverage) / 2
        }


def analyze_file(file_path: Path) -> TypeAnnotationAnalyzer:
    """分析单个文件的类型注解"""
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read())
            analyzer = TypeAnnotationAnalyzer()
            analyzer.visit(tree)
            return analyzer
        except SyntaxError:
            return TypeAnnotationAnalyzer()


def analyze_directory(directory: Path) -> Dict[str, any]:
    """分析目录下所有Python文件的类型注解"""
    results = {
        'files': [],
        'total_functions': 0,
        'total_classes': 0,
        'annotated_functions': 0,
        'annotated_classes': 0
    }

    for py_file in directory.rglob('*.py'):
        if 'venv' in str(py_file) or '.venv' in str(py_file):
            continue

        analyzer = analyze_file(py_file)
        results['files'].append({
            'path': str(py_file),
            'coverage': analyzer.get_coverage()
        })
        results['total_functions'] += analyzer.total_functions
        results['total_classes'] += analyzer.total_classes
        results['annotated_functions'] += analyzer.annotated_functions
        results['annotated_classes'] += analyzer.annotated_classes

    return results


def print_report(results: Dict[str, any]) -> None:
    """打印分析报告"""
    print("=" * 60)
    print("类型注解覆盖率分析报告")
    print("=" * 60)
    
    total_funcs = results['total_functions']
    total_classes = results['total_classes']
    annotated_funcs = results['annotated_functions']
    annotated_classes = results['annotated_classes']
    
    func_coverage = (annotated_funcs / total_funcs * 100) if total_funcs > 0 else 0
    class_coverage = (annotated_classes / total_classes * 100) if total_classes > 0 else 0
    
    print(f"\n总体统计:")
    print(f"  函数总数: {total_funcs}")
    print(f"  已注解函数: {annotated_funcs}")
    print(f"  函数覆盖率: {func_coverage:.2f}%")
    print(f"\n  类总数: {total_classes}")
    print(f"  已注解类: {annotated_classes}")
    print(f"  类覆盖率: {class_coverage:.2f}%")
    print(f"\n  总体覆盖率: {(func_coverage + class_coverage) / 2:.2f}%")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python type_annotation_tool.py <目录路径>")
        sys.exit(1)
    
    directory = Path(sys.argv[1])
    if not directory.exists():
        print(f"错误: 目录不存在: {directory}")
        sys.exit(1)
    
    print(f"分析目录: {directory}")
    results = analyze_directory(directory)
    print_report(results)


if __name__ == "__main__":
    main()
