"""策略版本管理 + Excel导出"""
import json, io
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
router = APIRouter()
_versions_store: dict[str, list] = {}

@router.post("/{strategy_id}/version")
async def save_version(strategy_id: str, note: str = Query("")):
    from app.api.v1.strategies import _strategies_store
    s = _strategies_store.get(strategy_id)
    if not s: raise HTTPException(404, "策略不存在")
    if strategy_id not in _versions_store: _versions_store[strategy_id] = []
    vn = len(_versions_store[strategy_id]) + 1
    _versions_store[strategy_id].append({"version":vn,"timestamp":datetime.utcnow().isoformat(),"note":note,"backtest":s.get("backtest"),"definition_summary":{"name":s["name"],"style":s.get("dynamic_style",s.get("style")),"factors":[{"name":f["name"],"weight":f["weight"]} for f in s.get("factors",[])]}})
    return {"strategy_id":strategy_id,"version":vn,"total_versions":len(_versions_store[strategy_id])}

@router.get("/{strategy_id}/versions")
async def get_versions(strategy_id: str):
    return {"strategy_id":strategy_id,"versions":_versions_store.get(strategy_id,[])}

@router.get("/{strategy_id}/export/excel")
async def export_excel(strategy_id: str):
    from app.api.v1.strategies import _strategies_store
    s = _strategies_store.get(strategy_id)
    if not s: raise HTTPException(404, "策略不存在")
    bt = s.get("backtest",{})
    try:
        import openpyxl
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "回测结果"
        ws.append(["策略名称",s.get("name","")])
        ws.append(["风格",s.get("dynamic_style",s.get("style",""))])
        ws.append([])
        ws.append(["指标","数值"])
        for k,v in [("年化收益率(%)",bt.get("annual_return_pct")),("最大回撤(%)",bt.get("max_drawdown_pct")),("夏普比率",bt.get("sharpe_ratio")),("胜率(%)",bt.get("win_rate_pct")),("交易次数",bt.get("total_trades")),("综合评分",bt.get("composite_score"))]: ws.append([k,v])
        ws.append([]); ws.append(["因子","权重"])
        for f in s.get("factors",[]): ws.append([f.get("name",""),f.get("weight",0)])
        output = io.BytesIO(); wb.save(output); output.seek(0)
        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition":f"attachment; filename={s['name']}.xlsx"})
    except ImportError: raise HTTPException(500, "openpyxl未安装")
