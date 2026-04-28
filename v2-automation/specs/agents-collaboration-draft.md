# 三Agent协作规格（毛坯版）

## 总流程
collector → analyzer → organizer 串行。手动触发还是定时触发？

## Agent职责
- collector: 抓GitHub Trending Top 10。存哪？文件名规则？
- analyzer: 读数据、打分、写摘要。如果采集数据为空怎么办？
- organizer: 整理成文章。需要去重吗？

## 协作契约（困惑）
- 数据怎么传递？文件还是直接传内容？
- 上游失败下游怎么办？
- 权限怎么分？