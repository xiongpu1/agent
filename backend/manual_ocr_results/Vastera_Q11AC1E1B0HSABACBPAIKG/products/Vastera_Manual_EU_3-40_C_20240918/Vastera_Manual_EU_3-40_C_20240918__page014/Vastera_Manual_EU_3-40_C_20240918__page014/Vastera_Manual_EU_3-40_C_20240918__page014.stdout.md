=====================
BASE:  torch.Size([1, 256, 1280])
PATCHES:  torch.Size([6, 100, 1280])
=====================
<|ref|>text<|/ref|><|det|>[[105, 133, 485, 149]]<|/det|>
In RGB mode, the working pattern is as follows:  

<|ref|>text<|/ref|><|det|>[[128, 157, 598, 292]]<|/det|>
State 1: automatic color change (cycle through state 2- 8) State 2: red State 3: green State 4: yellow (green+red) State 5: blue State 6: purple (blue+red) State 7: cyan (blue+green) State 8: white  

<|ref|>sub_title<|/ref|><|det|>[[82, 316, 201, 334]]<|/det|>
## 5. Circ pump  

<|ref|>text<|/ref|><|det|>[[102, 342, 703, 359]]<|/det|>
When the control system is turned on, the circ pump will run automatically.  

<|ref|>sub_title<|/ref|><|det|>[[82, 392, 165, 408]]<|/det|>
## 6. Ozone  

<|ref|>text<|/ref|><|det|>[[102, 417, 761, 434]]<|/det|>
The ozone will turn on and off automatically according to the control system state.  

<|ref|>text<|/ref|><|det|>[[101, 442, 907, 477]]<|/det|>
When the circ pump is running, zone will turn on. Then the circ pump is turned off, the ozone will turn off automatically.  

<|ref|>sub_title<|/ref|><|det|>[[82, 501, 180, 518]]<|/det|>
## 7. Heating  

<|ref|>text<|/ref|><|det|>[[102, 526, 671, 544]]<|/det|>
When the control system is turned on, heating will be on automatically.  

<|ref|>text<|/ref|><|det|>[[102, 552, 870, 586]]<|/det|>
When heating is turned on, circ pump will be started in advance. Then heat pump will run. When heating is turned off, heat pump turns off in advance and then circ pump.  

<|ref|>text<|/ref|><|det|>[[101, 594, 897, 629]]<|/det|>
When heating is turned on, the control system will automatically control the water temp by starting and stopping the heat pump according to water temp and setting temp.  

<|ref|>text<|/ref|><|det|>[[104, 636, 555, 653]]<|/det|>
Temp control regulation (when the system is turned on):  

<|ref|>text<|/ref|><|det|>[[128, 661, 905, 728]]<|/det|>
When water temp \(\geq\) set temp \(+1^{\circ}C\) ( \(34^{\circ}F\) ), then cooling function of the heat pump will be started. When water temp \(\geq\) set temp \(- 1^{\circ}C\) ( \(34^{\circ}F\) ), then heating function of the heat pump will be started. When water temp \(\geq\) set temp, then heat pump stops working.
==================================================
image size:  (1170, 1654)
valid image tokens:  781
output texts tokens (valid):  576
compression ratio:  0.74
==================================================
===============save results:===============