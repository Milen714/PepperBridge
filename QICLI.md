C:\Program Files (x86)\Softbank Robotics\Choregraphe Suite 2.8\bin>.\qicli.exe --qi-url=tcp://10.149.134.20:9559 call ALAutonomousLife.setState "solitary" null [W] 1788431535.389663 17840 qitype.signal: disconnect: No subscription found for SignalLink 14. [W] 1788431535.389663 25076 qitype.signal: disconnect: No subscription found for SignalLink 0. C:\Program Files (x86)\Softbank Robotics\Choregraphe Suite 2.8\bin>.\qicli.exe --qi-url=tcp://10.149.134.20:9559 call ALAutonomousLife.getState "solitary" [W] 1788431568.488032 40340 qitype.signal: disconnect: No subscription found for SignalLink 14. [W] 1788431568.488032 38228 qitype.signal: disconnect: No subscription found for SignalLink 0. C:\Program Files (x86)\Softbank Robotics\Choregraphe Suite 2.8\bin>.\qicli.exe --qi-url=tcp://10.149.134.20:9559 call ALAutonomousLife.getActivityContextPermissionViolations "boot-config/." [] [W] 1788431577.840460 38156 qitype.signal: disconnect: No subscription found for SignalLink 0. [W] 1788431577.840460 36920 qitype.signal: disconnect: No subscription found for SignalLink 14. C:\Program Files (x86)\Softbank Robotics\Choregraphe Suite 2.8\bin>.\qicli.exe --qi-url=tcp://10.149.134.20:9559 call ALAutonomousLife.switchFocus "boot-config/." null [W] 1788431598.115601 39356 qitype.signal: disconnect: No subscription found for SignalLink 0. [W] 1788431598.115601 24224 qitype.signal: disconnect: No subscription found for SignalLink 14. C:\Program Files (x86)\Softbank Robotics\Choregraphe Suite 2.8\bin>

cd C:\Program Files (x86)\Softbank Robotics\Choregraphe Suite 2.8\bin

.\qicli.exe --qi-url=tcp://172.28.111.16:9559 call ALAutonomousLife.setState "solitary"

.\qicli.exe --qi-url=tcp://172.28.111.16:9559 call ALAutonomousLife.getActivityContextPermissionViolations "boot-config/."

.\qicli.exe --qi-url=tcp://172.28.111.16:9559 call ALAutonomousLife.switchFocus "boot-config/."

set PYTHONPATH=C:\PepperSDK\pynaoqi-python2.7-2.8.7.4-win64-vs2015-20210818_210634\lib

dir "%PYTHONPATH%\naoqi.py"

C:\Python27\python.exe test.py
