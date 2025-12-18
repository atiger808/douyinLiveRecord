# -*- coding: utf-8 -*-
# @File   :config.py
# @Time   :2025/11/25 16:21
# @Author :admin


gen_startup_cmd = r'''
@echo off
color 0a
title 抖学智能体
setlocal enabledelayedexpansion
chcp 936
cls

REM 切换到脚本所在目录

REM 激活虚拟环境
CALL "miniconda3\Scripts\activate.bat" avatar

REM 设置FFMPEG环境变量
SET "FFMPEG_PATH=ffmpeg\bin"
SET "PATH=%PATH%;%FFMPEG_PATH%"

REM 设置ImageMagick环境变量
SET "IMAGE_PATH=ImageMagick-7.1.1-Q16-HDRI"
SET "PATH=%PATH%;%IMAGE_PATH%"
SET "IMAGEMAGICK_BINARY=ImageMagick-7.1.1-Q16-HDRI\magick.exe"

REM 启动后端服务
START /b "" "%~dp0miniconda3\envs\avatar\python.exe" "%~dp0start_robot.py"

REM 等待服务器启动
ECHO 正在等待服务器启动，请稍等...
timeout /t 5 /nobreak

REM 查找Chrome浏览器路径
SET "CHROME_PATH="

IF "%CHROME_PATH%"=="" (
    IF EXIST "C:\Program Files\Google\Chrome\Application\chrome.exe" (
        SET "CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
    ) ELSE IF EXIST "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
        SET "CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ) ELSE IF EXIST "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
        SET "CHROME_PATH=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
    )
)

REM 启动浏览器或提示手动访问
IF "%CHROME_PATH%"=="" (
    ECHO 未找到Chrome浏览器，请手动打开浏览器并访问 http://127.0.0.1:8000
    ECHO 服务器已在后台启动，您可以使用任何浏览器访问上述地址。
) ELSE (
    SET "CHROME_USER_DATA=%LOCALAPPDATA%\Google\Chrome\User Data"
    ECHO 启动Chrome浏览器: %CHROME_PATH%
    ECHO 使用Chrome配置目录: %CHROME_USER_DATA%
    START "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%CHROME_USER_DATA%" http://127.0.0.1:8000
)

ECHO.
ECHO 抖学智能体服务已启动，您可以关闭此窗口。
ECHO 如需退出程序，请关闭服务器窗口和浏览器。
'''



file_version_info_cmd = r'''
# UTF-8
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers=(FILEVERS),
    prodvers=(FILEVERS),
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x40004,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x2,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'COMPANY_NAME'),
        StringStruct(u'FileDescription', u'PRODUCT_DESCRIPTION'),
        StringStruct(u'FileVersion', u'VERSION_NO'),
        StringStruct(u'InternalName', u'PRODUCT_NAME'),
        StringStruct(u'LegalCopyright', u'Copyright © 2025 COMPANY_NAME'),
        StringStruct(u'OriginalFilename', u'PRODUCT_NAME.exe'),
        StringStruct(u'ProductName', u'PRODUCT_NAME'),
        StringStruct(u'ProductVersion', u'VERSION_NO')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
'''