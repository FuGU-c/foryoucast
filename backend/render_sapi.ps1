param([Parameter(Mandatory=$true)][string]$InputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$request = Get-Content -LiteralPath $InputPath -Raw -Encoding UTF8 | ConvertFrom-Json
$language = [string]$request.language
$baseLanguage = $language.Split('-')[0]
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voices = @($synth.GetInstalledVoices() | Where-Object {
        $_.Enabled -and $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq $baseLanguage
    } | ForEach-Object { $_.VoiceInfo })
    if ($voices.Count -eq 0) { throw "No installed System.Speech voice for language $language" }
    $maya = @($voices | Sort-Object @{Expression={if ($_.Gender -eq 'Female') {0} else {1}}}, Name)[0]
    $others = @($voices | Where-Object { $_.Name -ne $maya.Name } | Sort-Object @{Expression={if ($_.Gender -eq 'Male') {0} else {1}}}, Name)
    $leo = $maya
    if ($others.Count -gt 0) { $leo = $others[0] }
    $rendered = @()
    $index = 0
    foreach ($turn in $request.turns) {
        if ($turn.speaker -notin @('maya', 'leo') -or [string]::IsNullOrWhiteSpace($turn.text)) {
            throw 'An approved turn has no valid speaker or text'
        }
        $voice = $maya
        if ($turn.speaker -eq 'leo') { $voice = $leo }
        $filename = 'turn-{0:D4}.wav' -f $index
        $targetPath = Join-Path -Path $request.output_directory -ChildPath $filename
        $synth.SelectVoice($voice.Name)
        $synth.Rate = 0
        $synth.Volume = 100
        $synth.SetOutputToWaveFile($targetPath)
        # Speak is plain text. No SSML, command interpolation, or evaluation.
        $synth.Speak([string]$turn.text)
        $synth.SetOutputToNull()
        $rendered += @{file=$filename; voice_id=$voice.Name; culture=$voice.Culture.Name}
        $index++
    }
    @{turns=$rendered} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $request.result_path -Encoding UTF8
} finally {
    $synth.Dispose()
}
