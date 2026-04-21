"""Shared site presets for GUI and Web UI launchers."""

GUI_SITE_PRESETS = {
    "직접 URL 입력": "",
    "인터파크": "https://tickets.interpark.com",
    "예스24": "https://ticket.yes24.com",
    "멜론티켓": "https://ticket.melon.com",
    "티켓링크": "https://www.ticketlink.co.kr",
}

WEB_SITE_PRESETS = {
    "custom": "",
    "interpark": GUI_SITE_PRESETS["인터파크"],
    "yes24": GUI_SITE_PRESETS["예스24"],
    "melon": GUI_SITE_PRESETS["멜론티켓"],
    "ticketlink": GUI_SITE_PRESETS["티켓링크"],
}
