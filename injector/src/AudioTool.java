package com.tcl.tchord.optimizer;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * TCL T-Chord In-Memory Audio HAL Injector & CEC TRD Query Tool (v3.1.0)
 *
 * Binary-verified on TCL 75Q9M Pro (MT9655 / Android 14):
 * - Speaker_MsePeq: 13 hardware biquads (Band 1..8 owned by TCL/AIAQ; Band 9..13 immune)
 * - AQ_PEQ_PARAM  : Type 0=Peaking (Q/10), 1=HPF (Q/100), 2=LPF (Q/100), 3=LS, 4=HS; Gain in 0.1 dB
 * - VolumeOffset  : AQ_OUTPUT_VOL_OFFSET=1;OutputVolumeOffset=<0.1dB>;AQ_DEVICE=SpeakerOutput
 * - String bools  : AQ_TCSE_ENABLE / AQ_DolbyDialogEnhancerEnable / AQ_DolbyVolumeLevler => "On"/"Off"
 */
public class AudioTool {

    private static Method sGetParametersMethod;
    private static Method sSetParametersMethod;

    static {
        try {
            Class<?> audioSystem = Class.forName("android.media.AudioSystem");
            sGetParametersMethod = audioSystem.getMethod("getParameters", String.class);
            sSetParametersMethod = audioSystem.getMethod("setParameters", String.class);
        } catch (Throwable t) {
            System.err.println("[-] Failed to initialize AudioSystem reflection: " + t.getMessage());
        }
    }

    public static String get(String key) {
        if (sGetParametersMethod == null) return "";
        try {
            Object res = sGetParametersMethod.invoke(null, key);
            return res == null ? "" : res.toString();
        } catch (Throwable t) {
            System.err.println("[-] AudioSystem.getParameters failed: " + t.getMessage());
            return "";
        }
    }

    public static int set(String keyValuePairs) {
        if (sSetParametersMethod == null) return -1;
        try {
            return (Integer) sSetParametersMethod.invoke(null, keyValuePairs);
        } catch (Throwable t) {
            System.err.println("[-] AudioSystem.setParameters failed: " + t.getMessage());
            return -1;
        }
    }

    private static int handleSet(String kv) {
        int ret = set(kv);
        System.out.println("SET [" + kv + "] => ret=" + ret);
        return ret;
    }

    private static void executeBatch(List<String> commands) {
        int failCount = 0;
        for (String cmd : commands) {
            if (cmd == null || cmd.trim().isEmpty()) continue;
            if (handleSet(cmd.trim()) != 0) {
                failCount++;
            }
        }
        if (failCount > 0) {
            System.err.println("[-] Error: " + failCount + " Audio HAL parameter(s) returned non-zero.");
            System.exit(2);
        }
    }

    /**
     * Apply calibrated v3.1 PBA T-Chord profile to TV SpeakerOutput.
     * Args:
     *   args[1] (optional): vol_offset_tenth_db (default "-80" => -8.0 dB)
     *   args[2] (optional): pipe-delimited PEQ commands
     *   args[3] (optional): pipe-delimited extra HAL commands
     */
    private static void handleApplyCalibratedProfile(String[] args) {
        int volOffsetTenthDb = -80; // -8.0 dB in 0.1 dB units
        List<String> peqCommands = new ArrayList<>();
        List<String> extraCommands = new ArrayList<>();

        if (args.length > 1 && args[1] != null && !args[1].trim().isEmpty()) {
            try {
                volOffsetTenthDb = Integer.parseInt(args[1].trim());
            } catch (NumberFormatException e) {
                System.err.println("[!] Invalid vol_offset_tenth_db '" + args[1] + "', using -80 (-8.0 dB)");
            }
        }
        if (args.length > 2 && args[2] != null && !args[2].trim().isEmpty()) {
            for (String p : args[2].split("\\|\\|")) {
                if (!p.trim().isEmpty()) peqCommands.add(p.trim());
            }
        }
        if (args.length > 3 && args[3] != null && !args[3].trim().isEmpty()) {
            for (String e : args[3].split("\\|\\|")) {
                if (!e.trim().isEmpty()) extraCommands.add(e.trim());
            }
        }

        if (peqCommands.isEmpty()) {
            // Default v3.1 Perceptual Band Allocation (PBA) on AIAQ-immune Band 9..13
            peqCommands.add("AQ_PEQ_PARAM=1;Fc=300;Type=1;AQ_DEVICE=SpeakerOutput;Q=71;Band=9;Gain=0;Enable=1");
            peqCommands.add("AQ_PEQ_PARAM=1;Fc=300;Type=1;AQ_DEVICE=SpeakerOutput;Q=71;Band=10;Gain=0;Enable=1");
            peqCommands.add("AQ_PEQ_PARAM=1;Fc=1000;Type=0;AQ_DEVICE=SpeakerOutput;Q=10;Band=11;Gain=-20;Enable=1");
            peqCommands.add("AQ_PEQ_PARAM=1;Fc=4000;Type=0;AQ_DEVICE=SpeakerOutput;Q=14;Band=12;Gain=20;Enable=1");
            peqCommands.add("AQ_PEQ_PARAM=1;Fc=8000;Type=0;AQ_DEVICE=SpeakerOutput;Q=14;Band=13;Gain=15;Enable=1");
        }

        List<String> commands = new ArrayList<>();
        commands.add("AQ_TCSE_Speech_Clear=0");
        commands.add("AQ_OUTPUT_VOL_OFFSET=1;OutputVolumeOffset=" + volOffsetTenthDb + ";AQ_DEVICE=SpeakerOutput");
        commands.addAll(peqCommands);
        commands.addAll(extraCommands);

        executeBatch(commands);
        System.out.println("[+] Dispatched " + commands.size() + " HAL commands (verify via logcat).");
    }

    private static void handleRestoreDefaults() {
        List<String> commands = new ArrayList<>();
        for (int b = 9; b <= 13; b++) {
            commands.add("AQ_PEQ_PARAM=1;Fc=1000;Type=0;AQ_DEVICE=SpeakerOutput;Q=10;Band=" + b + ";Gain=0;Enable=0");
        }
        for (int b = 1; b <= 4; b++) {
            commands.add("AQ_PEQ_PARAM=1;Fc=1000;Type=0;AQ_DEVICE=SpeakerOutput;Q=10;Band=" + b + ";Gain=0;Enable=0");
        }
        commands.add("AQ_OUTPUT_VOL_OFFSET=1;OutputVolumeOffset=0;AQ_DEVICE=SpeakerOutput");
        commands.add("AQ_TCSE_Speech_Clear=0");
        commands.add("AQ_TCSE_VERTICAL_SOUND_FIELD_MODE=0");
        commands.add("AQ_DolbyDialogEnhancerEnable=Off");
        commands.add("AQ_DolbyVolumeLevler=Off");

        executeBatch(commands);
        System.out.println("[+] HAL defaults restored.");
    }

    private static void handleQuerySoundbarCec() {
        try {
            Class<?> clientClass = Class.forName("android.hardware.hdmi.TclHdmiTvClient");
            Object client = clientClass.getDeclaredConstructor().newInstance();

            String[] methods = {
                "getAvrDeviceIsTSymphony",
                "getAvrDeviceIsTrd",
                "getTclReadyVersion",
                "getEarcStatus",
                "getSbarBrandNameCode",
                "getSbarCustomControlCapabilities",
                "getTrdDeviceEqMode",
                "getTrdDeviceEqList",
                "getDialogEnhancer",
                "getNightMode",
                "getBassEnhancer",
                "getSurroundVirtualizer",
                "getSurroundSpeakerVol",
                "getDefinition",
                "getAiSonic",
                "getTclReadyDeviceInfo",
                "getTclReadyFeature"
            };

            for (String mName : methods) {
                try {
                    Object val = clientClass.getMethod(mName).invoke(client);
                    System.out.println("CEC " + mName + " => " + (val == null ? "null" : val.toString()));
                } catch (Throwable inner) {
                    Throwable cause = inner.getCause() != null ? inner.getCause() : inner;
                    System.out.println("CEC " + mName + " => <err: " + cause.getClass().getSimpleName() + ">");
                }
            }
        } catch (Throwable t) {
            Throwable cause = t.getCause() != null ? t.getCause() : t;
            System.out.println("CEC_UNAVAILABLE: " + cause.getClass().getSimpleName() + ": " + cause.getMessage());
        }
    }

    public static void main(String[] args) {
        if (args.length == 0) {
            System.out.println("TCL T-Chord AudioTool v3.1.0");
            System.out.println("Usage: get <k> | set <k=v> | set_batch '<a||b>' | apply_calibrated_profile [tenth_db] [peq] [extra] | restore_defaults | query_soundbar_cec");
            return;
        }
        try {
            switch (args[0]) {
                case "get":
                    if (args.length < 2) System.exit(1);
                    System.out.println("GET " + args[1] + " => " + get(args[1]));
                    break;
                case "set":
                    if (args.length < 2) System.exit(1);
                    if (handleSet(args[1]) != 0) System.exit(2);
                    break;
                case "set_batch":
                    if (args.length < 2) System.exit(1);
                    executeBatch(Arrays.asList(args[1].split("\\|\\|")));
                    break;
                case "apply_calibrated_profile":
                    handleApplyCalibratedProfile(args);
                    break;
                case "restore_defaults":
                    handleRestoreDefaults();
                    break;
                case "query_soundbar_cec":
                    handleQuerySoundbarCec();
                    break;
                default:
                    System.err.println("Unknown command: " + args[0]);
                    System.exit(1);
            }
        } catch (Throwable t) {
            System.err.println("[-] Execution failed: " + t.getMessage());
            System.exit(3);
        }
    }
}
