#说在前面

本地部署大模型需要GPU支持，请确定电脑有GPU，并已安装CUDA，确保至少有2G的显存。



#AIGC本地部署大模型

适用于毕业论文AIGC检测，可以显示每段的ai率，使用AIGC_detector_zhv3模型，根据中文做了适配优化，对中文更友好，检测精度高，精度逼近知网等一众闭源大模型。
适合论文正式投稿前的初级AI率检测，完全免费！



#使用教程

强烈建议小白下载右侧Release中已经构建好的版本，自带模型，下载解压后双击AIGC Text.exe程序即可使用，可以拖入文档，点击左下角按钮等待一段时间后显示结果。



#构建教程

因模型文件过大仓库中并不带有模型，模型下载可以去 https://huggingface.co/yuchuantian/AIGC_detector_zhv3/tree/main 下载，并把文件放入根目录下的AIGC_Model文件夹，也可以直接网页搜索AIGC_detector_zhv3 进入作者的仓库进行下载，放入模型后安装所需要的库，可以使用命令调取requirements.txt文件自动安装，准备就绪后运行主程序main.py


