# Source:  https://github.com/SirRamEsq/SmartShape2D/blob/master/addons/diagnosticlist/utils.gd
# Repo:    SirRamEsq/SmartShape2D (star 1761) | License: MIT | Collected: 2026-10-29
# Commit:  9617190250d0
@tool
extends RefCounted
class_name DiagnosticList_Utils


const ENABLE_DEBUG_LOG: bool = false


static func log_debug(text: String) -> void:
    if ENABLE_DEBUG_LOG:
        print("[DiagnosticList] ", text)


static func log_error(text: String) -> void:
    push_error("[DiagnosticList] ", text)


static func sort_by_severity(a: DiagnosticList_Diagnostic, b: DiagnosticList_Diagnostic) -> bool:
    if a.severity == b.severity:
        return a.res_uri < b.res_uri
    return a.severity < b.severity


static func sort_by_uri(a: DiagnosticList_Diagnostic, b: DiagnosticList_Diagnostic) -> bool:
    return a.res_uri < b.res_uri
