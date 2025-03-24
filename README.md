
使用方法参见原项目链接 https://github.com/nicekate/mistral-ocr
convert2.py增加了一个对于50MB以上的文件自动拆分成多个文件喂给Mistral，并且在返回结果后合并成一个文件的逻辑 并且新增了GUI，可以支持拖拽入文件/文件管理器选择文件，批量处理。mistral密钥会被本地持久化保存。

---
this repository is a fork of nicekate/mistral-ocr.For pdf larger than 50MB,convert2.py split it into smaller chunks and merge them together to resolve the limitation of mistral api.what's more the convert2.py offers a user friendly GUI interface that allows users to 
drag in/select in file explorer and do batch processing.
