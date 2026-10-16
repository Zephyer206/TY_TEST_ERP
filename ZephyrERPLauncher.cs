using System;
using System.Diagnostics;
using System.IO;
using System.Linq;

namespace ZephyrERPLauncher
{
    class Program
    {
        static void Main(string[] args)
        {
            try
            {
                // Get the directory where the EXE is located (project root)
                string exeDirectory = AppDomain.CurrentDomain.BaseDirectory;

                // Find the PowerShell script dynamically to avoid encoding issues
                string[] psScripts = Directory.GetFiles(exeDirectory, "ZephyrERP*.ps1");

                if (psScripts.Length == 0)
                {
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine("Error: Cannot find ZephyrERP PowerShell script in directory:");
                    Console.WriteLine(exeDirectory);
                    Console.ResetColor();
                    Console.WriteLine("\nPress any key to exit...");
                    Console.ReadKey();
                    Environment.Exit(1);
                    return;
                }

                if (psScripts.Length > 1)
                {
                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.WriteLine("Warning: Multiple ZephyrERP PowerShell scripts found:");
                    foreach (var script in psScripts)
                    {
                        Console.WriteLine("  " + Path.GetFileName(script));
                    }
                    Console.ResetColor();
                    Console.WriteLine("\nPress any key to exit...");
                    Console.ReadKey();
                    Environment.Exit(1);
                    return;
                }

                string scriptPath = psScripts[0];

                // Launch PowerShell with the script
                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments = string.Format("-ExecutionPolicy Bypass -NoProfile -File \"{0}\"", scriptPath),
                    WorkingDirectory = exeDirectory,
                    UseShellExecute = false,
                    CreateNoWindow = false
                };

                Process process = Process.Start(psi);
                if (process != null)
                {
                    process.WaitForExit();
                    Environment.Exit(process.ExitCode);
                }
                else
                {
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine("Error: Failed to start PowerShell process");
                    Console.ResetColor();
                    Console.WriteLine("\nPress any key to exit...");
                    Console.ReadKey();
                    Environment.Exit(1);
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("Error: " + ex.Message);
                Console.ResetColor();
                Console.WriteLine("\nPress any key to exit...");
                Console.ReadKey();
                Environment.Exit(1);
            }
        }
    }
}
