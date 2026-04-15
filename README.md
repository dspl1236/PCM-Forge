# PCM-Forge

**Reverse engineering toolkit for Porsche PCM 3.1 infotainment systems**

Targeting the Harman Becker PCM 3.1 found in 2011-2016 Porsche vehicles:
- Cayenne (958)
- Panamera (970)
- 911 (991.1)
- Boxster/Cayman (981)
- Macan (95B)

## Status: Early Research

This project is in the research phase. We're documenting the PCM 3.1 hardware and software architecture, identifying entry points for custom code execution, and building diagnostic tools.

## What We Know So Far

| Detail | Info |
|--------|------|
| Manufacturer | Harman Becker Automotive Systems |
| FCC ID | T8G-BE96XX |
| OS | QNX RTOS (likely 6.3 or 6.5) |
| Display | 7" 800×480 touchscreen |
| Input | Rotary knob + touchscreen + soft keys |
| Storage | Internal HDD (SATA) |
| USB | Single USB port |
| Engineering Menu | Boots from prepared USB stick |
| Diagnostic Tool | PIWIS (Porsche dealer tool) |
| CAN Bus | V850 IOC gateway (same as Audi MMI3G) |
| Relation | Sister platform to Audi MMI3G (same manufacturer, same era) |

## Engineering Menu Access

The PCM 3.1 has a hidden engineering/service menu that is accessible by booting from a specially prepared USB stick. This menu allows:
- Navigation database switching
- Software activation codes
- Feature enable/disable
- Firmware version display

Access method under investigation. Some reports indicate `Source + Sound` button combo may also trigger it on certain firmware versions.

## Architecture (Estimated)

Based on the Harman Becker relationship with the Audi MMI3G platform:

```
┌─────────────────────────────────────────┐
│           Porsche PCM 3.1               │
│                                         │
│  ┌──────────────┐   ┌───────────────┐   │
│  │  QNX RTOS    │   │  V850 IOC     │   │
│  │  Main CPU    │◄─►│  CAN Gateway  │   │
│  │  (J9 JVM?)   │   │  (all buses)  │   │
│  └──────────────┘   └───────────────┘   │
│         │                    │           │
│    ┌────┴────┐         ┌────┴────┐      │
│    │ Display │         │ CAN Bus │      │
│    │ 800x480 │         │Powertrain│     │
│    │  Touch  │         │Comfort   │     │
│    └─────────┘         │Infotain. │     │
│                        └─────────┘      │
└─────────────────────────────────────────┘
```

## Shared Code with MMI3G-Toolkit

The UDS diagnostic protocol stack is shared between platforms since both use VAG diagnostic addressing:

- `shared/uds/` — UDS protocol implementation (ISO 14229)
- `shared/transport/` — Transport layer abstraction
- `shared/scanner/` — VAG module scanner and database

See [MMI3G-Toolkit](https://github.com/dspl1236/MMI3G-Toolkit) for the full Audi implementation.

## Research Priorities

1. **Confirm internal architecture** — Is it QNX + J9 JVM like the MMI3G?
2. **USB engineering boot** — What file structure triggers engineering mode?
3. **Firmware dump** — Get system info from a running PCM 3.1
4. **CAN bus access** — Can we read/send diagnostic messages?
5. **Code execution** — Can we run custom code from USB?

## Supported Vehicles

| Model | Years | PCM Version | Status |
|-------|-------|-------------|--------|
| Cayenne (958) | 2011-2016 | PCM 3.1 | Target |
| Panamera (970) | 2011-2016 | PCM 3.1 | Compatible |
| 911 (991.1) | 2012-2016 | PCM 3.1 | Compatible |
| Boxster (981) | 2013-2016 | PCM 3.1 | Compatible |
| Cayman (981) | 2013-2016 | PCM 3.1 | Compatible |
| Macan (95B) | 2014-2016 | PCM 3.1 | Compatible |

Note: PCM 4.x (MIB2-based) is a different platform already covered by the [M.I.B. project](https://github.com/Mr-MIBonk/M.I.B._More-Incredible-Bash).

## Related Projects

- [MMI3G-Toolkit](https://github.com/dspl1236/MMI3G-Toolkit) — Sister project for Audi MMI3G/3G+
- [M.I.B.](https://github.com/Mr-MIBonk/M.I.B._More-Incredible-Bash) — For PCM 4.x / MIB2 systems
- [IOActive V850 Research](https://ioactive.com/wp-content/uploads/pdfs/IOActive_Remote_Car_Hacking.pdf) — V850 IOC reverse engineering methodology

## License

MIT License — See [LICENSE](LICENSE)

## Disclaimer

This toolkit is for research and educational purposes. Use at your own risk. Always maintain backups before modifying any vehicle system. The authors are not responsible for any damage to vehicles or components.
