package com.tcl.tchord.optimizer;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * TCL T-Chord In-Memory Parameter Injector & Audio HAL Tool (v2.1.1)
 *
 * Interacts directly with Android's hidden android.media.AudioSystem via reflection.
 * Fully volatile and non-destructive: zero disk writes, 100% RAM-only.
 *
 * Features & Reliability Safeguards:
 * - Real -8dB ICLD attenuation via AQ_OUTPUT_VOL_OFFSET=<db>;AQ_DEVICE=SpeakerOutput
 * - Dynamic PEQ configuration passed directly from JSON configuration
 * - Bundled AQ_TCSE_TUTTI_CHORAL_SBAR_CHANNEL to eliminate vendor HAL return code bug
 * - Non-zero exit code (System.exit(2)) on any AudioSystem failure to prevent false positives
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
            return (String) sGetParametersMethod.invoke(null, key);
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

    private static void handleGet(String key) {
        String val = get(key);
        System.out.println("GET " + key + " => " + (val == null ? "" : val));
    }

    private static int handleSet(String kv) {
        int ret = set(kv);
        System.out.println("SET [" + kv + "] => ret=" + ret);
        return ret;
    }

    private static void handleApplyCalibratedProfile(String[] args) throws Exception {
        System.out.println("=====================================================");
        System.out.println(" Applying Calibrated T-Chord Acoustic Profile (RAM)  ");
        System.out.println("=====================================================");

        String latencies = "42,58,66,80,84,92,74,54,82,50,50";
        int volOffsetDb = -8;
        List<String> peqCommands = new ArrayList<>();

        if (args.length > 1 && args[1] != null && !args[1].trim().isEmpty()) {
            latencies = args[1].trim();
        }
        if (args.length > 2 && args[2] != null && !args[2].trim().isEmpty()) {
            try {
                volOffsetDb = Integer.parseInt(args[2].trim());
            } catch (NumberFormatException ignored) {}
        }
        if (args.length > 3 && args[3] != null && !args[3].trim().isEmpty()) {
            String[] peqs = args[3].split("\\|\\|");
            for (String p : peqs) {
                if (!p.trim().isEmpty()) {
                    peqCommands.add(p.trim());
                }
            }
        }

        if (peqCommands.isEmpty()) {
            peqCommands.add("AQ_PEQ_PARAM=1;Fc=480;Type=2;AQ_DEVICE=SpeakerOutput;Q=71;Band=1;Gain=0;Enable=1");
            peqCommands.add("AQ_PEQ_PARAM=1;Fc=480;Type=2;AQ_DEVICE=SpeakerOutput;Q=71;Band=2;Gain=0;Enable=1");
            peqCommands.add("AQ_PEQ_PARAM=1;Fc=3500;Type=0;AQ_DEVICE=SpeakerOutput;Q=150;Band=3;Gain=3;Enable=1");
        }

        List<String> commands = new ArrayList<>();
        commands.add("AQ_TCSE_ENABLE=1");
        commands.add("AQ_TCSE_TUTTI_CHORAL_MODE=1");
        commands.add("AQ_TCSE_Speech_Clear=1");
        commands.add("AQ_TCSE_VERTICAL_SOUND_FIELD_MODE=1");
        commands.add("AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY=" + latencies + ";AQ_TCSE_TUTTI_CHORAL_SBAR_CHANNEL=16777215");
        commands.add("AQ_OUTPUT_VOL_OFFSET=" + volOffsetDb + ";AQ_DEVICE=SpeakerOutput");
        commands.addAll(peqCommands);

        int failCount = 0;
        for (String cmd : commands) {
            int ret = handleSet(cmd);
            if (ret != 0) {
                failCount++;
            }
        }

        if (failCount > 0) {
            System.err.println("[-] Error: " + failCount + " Audio HAL parameter(s) failed with non-zero return code.");
            System.exit(2);
        }

        System.out.println("[+] Calibrated profile successfully loaded into Audio HAL.");
    }

    private static void handleRestoreDefaults() {
        System.out.println("[*] Restoring TV Audio HAL to factory defaults...");
        List<String> commands = Arrays.asList(
            "AQ_PEQ_PARAM=1;Fc=1000;Type=0;AQ_DEVICE=SpeakerOutput;Q=160;Band=1;Gain=0;Enable=0",
            "AQ_PEQ_PARAM=1;Fc=1000;Type=0;AQ_DEVICE=SpeakerOutput;Q=160;Band=2;Gain=0;Enable=0",
            "AQ_PEQ_PARAM=1;Fc=1000;Type=0;AQ_DEVICE=SpeakerOutput;Q=160;Band=3;Gain=0;Enable=0",
            "AQ_OUTPUT_VOL_OFFSET=0;AQ_DEVICE=SpeakerOutput",
            "AQ_TCSE_Speech_Clear=0",
            "AQ_TCSE_VERTICAL_SOUND_FIELD_MODE=0"
        );

        int failCount = 0;
        for (String cmd : commands) {
            int ret = handleSet(cmd);
            if (ret != 0) {
                failCount++;
            }
        }

        if (failCount > 0) {
            System.err.println("[-] Warning: Failed to restore " + failCount + " parameter(s).");
            System.exit(2);
        }

        System.out.println("[+] Defaults restored.");
    }

    private static void handleQueryStatus() {
        System.out.println("[*] Querying current audio properties...");
        String[] keys = {
            "AQ_TCSE_ENABLE",
            "AQ_TCSE_TUTTI_CHORAL_MODE",
            "AQ_TCSE_Speech_Clear",
            "AQ_TCSE_VERTICAL_SOUND_FIELD_MODE",
            "AQ_OUTPUT_VOL_OFFSET",
            "digital_out_on_off"
        };
        for (String k : keys) {
            handleGet(k);
        }
    }

    public static void main(String[] args) {
        if (args.length == 0) {
            printUsage();
            return;
        }

        String action = args[0];
        try {
            switch (action) {
                case "get":
                    if (args.length > 1) {
                        handleGet(args[1]);
                    } else {
                        System.err.println("Missing key argument for get");
                        System.exit(1);
                    }
                    break;
                case "set":
                    if (args.length > 1) {
                        int ret = handleSet(args[1]);
                        if (ret != 0) {
                            System.exit(2);
                        }
                    } else {
                        System.err.println("Missing parameter argument for set");
                        System.exit(1);
                    }
                    break;
                case "apply_calibrated_profile":
                    handleApplyCalibratedProfile(args);
                    break;
                case "restore_defaults":
                    handleRestoreDefaults();
                    break;
                case "query_status":
                    handleQueryStatus();
                    break;
                default:
                    System.err.println("Unknown command: " + action);
                    printUsage();
                    System.exit(1);
                    break;
            }
        } catch (Throwable t) {
            System.err.println("[-] Execution failed: " + t.getMessage());
            t.printStackTrace(System.err);
            System.exit(3);
        }
    }

    private static void printUsage() {
        System.out.println("TCL T-Chord In-Memory Optimizer Tool (v2.1.1)");
        System.out.println("Usage:");
        System.out.println("  app_process ... AudioTool get <key>");
        System.out.println("  app_process ... AudioTool set <key=value>");
        System.out.println("  app_process ... AudioTool apply_calibrated_profile [latencies_csv] [vol_offset_db] [peq_commands_pipe_delimited]");
        System.out.println("  app_process ... AudioTool restore_defaults");
        System.out.println("  app_process ... AudioTool query_status");
    }
}
