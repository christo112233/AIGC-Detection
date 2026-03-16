import os
import sys
import shutil
import subprocess

def main():
    print("🚀 准备开始构建")
    
    # 1. 检查必要环境
    try:
        import PyInstaller
    except ImportError:
        print("❌ 未检测到 PyInstaller，正在为您自动安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller 安装完成！")

    # 2. 定义路径与参数
    app_name = "DeepVeri"
    main_script = "main.py"
    model_folder = "AIGC_Model"
    icon_file = "logo.ico"
    
    if not os.path.exists(main_script):
        print(f"❌ 找不到主程序入口: {main_script}")
        return

    if not os.path.exists(model_folder):
        print(f"❌ 找不到模型文件夹: {model_folder}，请确保它存在于当前目录。")
        return

    print("\n📦 正在调用 PyInstaller 进行深度编译...")
    
    # PyInstaller 构建命令列表基础部分
    pyinstaller_args = [
        "pyinstaller",
        "--noconfirm",          
        "--onedir",             
        "--windowed",           
        f"--name={app_name}"    
    ]
    
    # 动态检测并添加程序图标
    if os.path.exists(icon_file):
        pyinstaller_args.append(f"--icon={icon_file}")
        print(f"🎨 已检测到图标文件 {icon_file}，将为程序注入专属图标！")
    else:
        print(f"⚠️ 未检测到 {icon_file}，将使用系统默认图标。")

    # 追加排除模块和主程序脚本
    pyinstaller_args.extend([
        #剔除 PySide6 未使用的庞大组件 ---
        "--exclude-module=PySide6.QtWebEngine",
        "--exclude-module=PySide6.QtWebEngineCore",
        "--exclude-module=PySide6.QtWebEngineWidgets",
        "--exclude-module=PySide6.QtNetwork",
        "--exclude-module=PySide6.QtQml",
        "--exclude-module=PySide6.QtSql",
        "--exclude-module=PySide6.QtMultimedia",
        "--exclude-module=PySide6.QtQuick",
        "--exclude-module=matplotlib",
        "--exclude-module=tkinter",
        
        main_script
    ])

    # 3. 执行打包过程
    try:
        subprocess.check_call(pyinstaller_args)
        print("\n✅ 代码编译完成！")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 打包过程发生错误: {e}")
        return

    dist_dir = os.path.join("dist", app_name)
    target_model_dir = os.path.join(dist_dir, model_folder)

    print(f"\n🚚 正在将庞大的 AI 模型挂载到发布版本中 (可能需要几秒钟)...")
    
    if os.path.exists(target_model_dir):
        print("清理旧的模型文件夹...")
        shutil.rmtree(target_model_dir)
        
    try:
        shutil.copytree(model_folder, target_model_dir)
        print("✅ 模型文件夹拷贝成功！")
    except Exception as e:
        print(f"❌ 模型拷贝失败: {e}")
        return

    # 5. 完成提示
    print("\n" + "="*50)
    print(f"🎉 打包大功告成！")
    print(f"📁 您的成品软件已输出至: {os.path.abspath(dist_dir)}")
    print(f"💡 发送给别人时，请将整个 【{app_name}】 文件夹打包成 ZIP 发送。")
    print(f"▶️ 用户解压后，双击里面的 【{app_name}.exe】 即可直接使用！")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()