Output demo/demo.gif
Output demo/demo.webm

Set Shell "bash"
Set FontSize 14
Set Width 100
Set Height 35
Set Theme "Molokai"
Set WindowBar Colorful
Set WindowBarSize 40
Set Padding 15
Set TypingSpeed 40ms

Type "# apple-a-day: Mac health checkup"
Enter
Sleep 500ms

Type "aad checkup --min-severity warning"
Enter
Sleep 18s

Type "# Agent-friendly JSON output"
Enter
Sleep 500ms

Type "aad checkup --json --min-severity critical --fields severity,summary,fix | head -20"
Enter
Sleep 18s

Type "# Runtime schema for agent discovery"
Enter
Sleep 500ms

Type "aad schema | head -12"
Enter
Sleep 3s

Sleep 2s
