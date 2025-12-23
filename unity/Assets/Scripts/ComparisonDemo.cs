using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// ComparisonDemo: splits screen into 5 viewports, runs path animations in parallel and shows timing UI.
/// Expect one main scene with five sub-cameras arranged horizontally.
/// </summary>
public class ComparisonDemo : MonoBehaviour
{
    public Camera mainCameraPrefab;
    public Transform[] scenarioRoots; // assign 5 transforms (or create at runtime)
    public string[] plannerNames = new string[5] {"ADAPTIVE","RRT*","HPA*","DSTAR","SAFETY"};
    public Text[] timeTexts; // UI Texts to show times for each pane
    public GameObject resultPanelPrefab;

    private Camera[] cams = new Camera[5];
    private float[] completionTimes = new float[5];
    private bool[] finished = new bool[5];

    void Start()
    {
        SetupCameras();
        StartCoroutine(RunComparison());
    }

    void SetupCameras()
    {
        for (int i = 0; i < 5; i++)
        {
            GameObject go = new GameObject("Cam"+i);
            var c = go.AddComponent<Camera>();
            c.rect = new Rect(i * 0.2f, 0, 0.2f, 1);
            cams[i] = c;
            // attach simple camera controls if desired
            var cc = go.AddComponent<CameraControl>();
            if (scenarioRoots != null && scenarioRoots.Length > i) cc.target = scenarioRoots[i];
        }
    }

    IEnumerator RunComparison()
    {
        // Wait a frame for all to initialize
        yield return null;

        float start = Time.time;
        // Start all animations by enabling PathAnimator components under scenarioRoots
        for (int i = 0; i < 5; i++)
        {
            if (scenarioRoots == null || scenarioRoots.Length <= i || scenarioRoots[i] == null) continue;
            var anim = scenarioRoots[i].GetComponentInChildren<PathAnimator>();
            if (anim != null) anim.enabled = true;
            finished[i] = false;
        }

        // Poll for completion
        while (true)
        {
            bool allDone = true;
            for (int i = 0; i < 5; i++)
            {
                var anim = scenarioRoots[i].GetComponentInChildren<PathAnimator>();
                if (anim == null) { continue; }
                if (anim.enabled)
                {
                    allDone = false;
                }
                else if (!finished[i])
                {
                    completionTimes[i] = Time.time - start;
                    finished[i] = true;
                    if (timeTexts != null && timeTexts.Length > i && timeTexts[i] != null)
                        timeTexts[i].text = string.Format("{0}: {1:F2}s", plannerNames[i], completionTimes[i]);
                }
            }
            if (allDone) break;
            yield return null;
        }

        // show ranking
        List<int> idx = new List<int>(); for (int i = 0; i < 5; i++) idx.Add(i);
        idx.Sort((a,b)=> completionTimes[a].CompareTo(completionTimes[b]));
        // instantiate result panel if provided
        if (resultPanelPrefab != null)
        {
            var panel = Instantiate(resultPanelPrefab, Vector3.zero, Quaternion.identity);
            var txt = panel.GetComponentInChildren<Text>();
            if (txt != null)
            {
                string s = "Ranking:\n";
                for (int i = 0; i < idx.Count; i++) s += string.Format("{0}. {1} ({2:F2}s)\n", i+1, plannerNames[idx[i]], completionTimes[idx[i]]);
                txt.text = s;
            }
        }
    }
}
