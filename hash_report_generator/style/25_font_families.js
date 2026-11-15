// Central Unicode font policy shared by every ReportLab report and page footer.
// Fonts are resolved from the operating system; no font binaries are redistributed.
module.exports = {
 FONT_FAMILIES: {regular:"ChronoUnicode",bold:"ChronoUnicodeBold",italic:"ChronoUnicodeItalic",bold_italic:"ChronoUnicodeBoldItalic",monospace:"ChronoUnicodeMono",monospace_bold:"ChronoUnicodeMonoBold"},
 FONT_FILES: {},
 FONT_POLICY: {require_embedded_unicode:true,fallback_to_builtin:false,
   system_font_candidates: {
    regular:["C:/Windows/Fonts/arial.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    bold:["C:/Windows/Fonts/arialbd.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    italic:["C:/Windows/Fonts/ariali.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"],
    bold_italic:["C:/Windows/Fonts/arialbi.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"],
    monospace:["C:/Windows/Fonts/consola.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"],
    monospace_bold:["C:/Windows/Fonts/consolab.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"]
   }
 }
};
