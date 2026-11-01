package com.tcl.tchord.optimizer;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/**
 * TCL T-Chord Joint Acoustic Optimizer - Native In-Memory Parameter Injector
 * 
 * Interacts directly with Android's android.media.AudioSystem and
 * android.hardware.hdmi.TclHdmiTvClient via reflection.
 * Runs non-invasively in memory via app_process, requiring zero flash modifications.
 */
public class AudioTool {

    private static final String DEFAULT_LATENCY_STRING = "42,58,66,80,84,92,74,54,82,50,50";

    public static void main(String[] args) {
        if (args.length == 0) {
            printUsage();
            return;
        }

        String command = args[0];
        try {
            switch (command) {
                case "get":
                    if (args.length > 1) {
                        handleGet(args[1]);
                    } else {
                        System.err.println("Error: 'get' requires a parameter key.");
                    }
                    break;

                case "set":
                    if (args.length > 1) {
                        handleSet(args[1]);
                    } else {
                        System.err.println("Error: 'set' requires a key=value pair.");
                    }
                    break;

                case "select_tsymphony":
                    handleSelectTSymphony();
                    break;

                case "apply_calibrated_profile":
                    handleApplyCalibratedProfile(args.length > 1 ? args[1] : DEFAULT_LATENCY_STRING);
                    break;

                case "restore_defaults":
                    handleRestoreDefaults();
                    break;

                case "query_status":
                    handleQueryStatus();
                    break;

                default:
                    System.err.println("Unknown command: " + command);
                    printUsage();
                    break;
            }
        } catch (Throwable t) {
            System.err.println("Fatal execution error: " + t.getMessage());
            t.printStackTrace();
        }
    }

    private static void printUsage() {
        System.out.println("TCL T-Chord In-Memory Optimizer Tool");
        System.out.println("Usage:");
        System.out.println("  app_process ... AudioTool get <key>");
        System.out.println("  app_process ... AudioTool set <key=value>");
        System.out.println("  app_process ... AudioTool select_tsymphony");
        System.out.println("  app_process ... AudioTool apply_calibrated_profile [latencies_csv]");
        System.out.println("  app_process ... AudioTool restore_defaults");
        System.out.println("  app_process ... AudioTool query_status");
    }

    private static void handleGet(String key) throws Exception {
        Class<?> audioSystem = Class.forName("android.media.AudioSystem");
        Method getParams = audioSystem.getMethod("getParameters", String.class);
        String res = (String) getParams.invoke(null, key);
        System.out.println("GET " + key + " => " + (res != null ? res : "<empty>"));
    }

    private static int handleSet(String kvp) throws Exception {
        Class<?> audioSystem = Class.forName("android.media.AudioSystem");
        Method setParams = audioSystem.getMethod("setParameters", String.class);
        Integer ret = (Integer) setParams.invoke(null, kvp);
        System.out.println("SET [" + kvp + "] => ret=" + ret);
        return ret != null ? ret : -1;
    }

    private static void handleSelectTSymphony() {
        try {
            System.out.println("[*] Invoking TclHdmiTvClient.selectTSymphonyOutput()...");
            Class<?> clz = Class.forName("android.hardware.hdmi.TclHdmiTvClient");
            Object client = clz.getDeclaredConstructor().newInstance();
            Method m = clz.getMethod("selectTSymphonyOutput");
            m.invoke(client);
            System.out.println("[+] T-Chord audio output selected via CEC client.");
        } catch (Throwable t) {
            System.err.println("[-] Failed to select T-Chord via CEC client: " + t.getMessage());
        }
    }

    private static void handleApplyCalibratedProfile(String latencyCsv) throws Exception {
        System.out.println("=====================================================");
        System.out.println(" Applying Calibrated T-Chord Acoustic Profile (RAM)  ");
        System.out.println("=====================================================");

        List<String> commands = new ArrayList<>();
        
        // 1. Enable TCSE & Tutti Choral Mode
        commands.add("AQ_TCSE_ENABLE=1");
        commands.add("AQ_TCSE_TUTTI_CHORAL_MODE=1");

        // 2. Enable Hardware Dialogue Intelligibility Engine
        commands.add("AQ_TCSE_Speech_Clear=1");
        commands.add("AQ_TCSE_VERTICAL_SOUND_FIELD_MODE=1");

        // 3. Inject 11-Slot Calibrated Latency Matrix
        commands.add("AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY=" + latencyCsv);

        // 4. Inject 480Hz Linkwitz-Riley Highpass PEQ (Band 1 & 2)
        commands.add("AQ_PEQ_PARAM=1;Fc=480;Type=2;AQ_DEVICE=SpeakerOutput;Q=71;Band=1;Gain=0;Enable=1");
        commands.add("AQ_PEQ_PARAM=1;Fc=480;Type=2;AQ_DEVICE=SpeakerOutput;Q=71;Band=2;Gain=0;Enable=1");

        // 5. Inject Blauert 3.5kHz Directional Elevation Boost (Band 3)
        commands.add("AQ_PEQ_PARAM=1;Fc=3500;Type=0;AQ_DEVICE=SpeakerOutput;Q=150;Band=3;Gain=3;Enable=1");

        for (String cmd : commands) {
            handleSet(cmd);
        }

        handleSelectTSymphony();
        System.out.println("[+] Calibrated profile successfully loaded into Audio HAL.");
    }

    private static void handleRestoreDefaults() throws Exception {
        System.out.println("[*] Restoring TV Audio HAL to factory defaults...");
        handleSet("AQ_PEQ_PARAM=1;Fc=1000;Type=0;AQ_DEVICE=SpeakerOutput;Q=160;Band=1;Gain=0;Enable=0");
        handleSet("AQ_PEQ_PARAM=1;Fc=1000;Type=0;AQ_DEVICE=SpeakerOutput;Q=160;Band=2;Gain=0;Enable=0");
        handleSet("AQ_PEQ_PARAM=1;Fc=1000;Type=0;AQ_DEVICE=SpeakerOutput;Q=160;Band=3;Gain=0;Enable=0");
        handleSet("AQ_TCSE_Speech_Clear=0");
        handleSet("AQ_TCSE_VERTICAL_SOUND_FIELD_MODE=0");
        System.out.println("[+] Defaults restored.");
    }

    private static void handleQueryStatus() throws Exception {
        System.out.println("[*] Querying current audio properties...");
        String[] keys = new String[] {
            "AQ_TCSE_ENABLE",
            "AQ_TCSE_TUTTI_CHORAL_MODE",
            "AQ_TCSE_Speech_Clear",
            "AQ_TCSE_VERTICAL_SOUND_FIELD_MODE",
            "digital_out_on_off"
        };
        for (String k : keys) {
            handleGet(k);
        }
    }
}
