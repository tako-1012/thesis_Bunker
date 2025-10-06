using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Sensor;
using Unity.Robotics.Core;


public class LaserScanPublishing : MonoBehaviour
{
    // Laser scanner parameters
    public int numberOfRays = 360; // Number of rays
    public float scanRange = 10f; // Maximum range
    public float minRange = 0.2f; // Minimum range
    public float scanAngle = 360f; // Total scan angle
    public LayerMask obstacleLayer; // Layers to detect
    public string frame_ID = "laser_scan_link"; // Frame ID for the laser

    // ROS connection
    public string topicName = "/laser_scan"; // ROS topic name
    public string clocktopicName = "/clock";
    private ROSConnection ros;

    // LaserScan data
    private float angleIncrement;
    private float[] ranges;

    // Publishing parameters
    public float publishingFrequency = 10f; // Frequency of publishing in Hz (10 publications per second)
    private float timeSinceLastPublish = 0f; // Time elapsed since the last publication

    void Start()
    {
        // Initialize ROS connection
        ros = ROSConnection.GetOrCreateInstance();
        ros.RegisterPublisher<LaserScanMsg>(topicName);
        
        // Calculate the angle increment between each ray
        angleIncrement = Mathf.Deg2Rad * (scanAngle / numberOfRays);

        // Initialize the range array with maximum values
        ranges = new float[numberOfRays];
    }

    void Update()
    {
        // Increment the elapsed time
        timeSinceLastPublish += Time.deltaTime;

        // Check if the time exceeds the desired publishing frequency
        if (timeSinceLastPublish >= 1f / publishingFrequency)
        {
            // Scan the environment
            ScanEnvironment();

            // Publish the laser scan data
            PublishLaserScan();

            // Reset the elapsed time
            timeSinceLastPublish = 0f;
        }
    }

    private void ScanEnvironment()
    {
        Vector3 startDirection = transform.forward; // Initial direction of the scanner


        for (int i = 0; i < numberOfRays; i++)
        {
            // Calculate the ray direction
            float angle = -scanAngle / 2f + (i * (scanAngle / numberOfRays));

            // Direction of the raycast based on the rotation
            Quaternion rotation = Quaternion.AngleAxis(-angle, transform.up);

            // Apply the rotation
            Vector3 rayDirection = rotation * startDirection;

            // Cast a ray
            if (Physics.Raycast(transform.position, rayDirection, out RaycastHit hit, scanRange, obstacleLayer))
            {
                // If an obstacle is detected and the distance is greater than the minimum range
                if (hit.distance >= minRange)
                {
                    ranges[i] = hit.distance;
                    // Debug.DrawRay(transform.position, rayDirection * hit.distance, Color.red);
                }
                else
                {
                    ranges[i] = Mathf.Infinity; // If the obstacle is too close
                    // Debug.DrawRay(transform.position, rayDirection * scanRange, Color.blue);
                }
            }
            else
            {
                ranges[i] = scanRange; // No obstacle detected
                // Debug.DrawRay(transform.position, rayDirection * scanRange, Color.green);
            }

            // if (i==0){
            //     Debug.DrawRay(transform.position, rayDirection * scanRange, Color.yellow);
            // }
        }
    }

    private void PublishLaserScan()
    {
        // Create the LaserScan message
        LaserScanMsg laserScan = new LaserScanMsg
        {
            header = new RosMessageTypes.Std.HeaderMsg
            {
                stamp = new TimeStamp(Clock.Now),
                frame_id = frame_ID // Frame ID
            },
            angle_min = -Mathf.Deg2Rad * (scanAngle / 2f), // Minimum angle
            angle_max = Mathf.Deg2Rad * (scanAngle / 2f), // Maximum angle
            angle_increment = angleIncrement, // Angle increment
            time_increment = 0f, // Time increment between scans (if needed)
            scan_time = Time.deltaTime, // Duration of a complete scan
            range_min = minRange, // Minimum range
            range_max = scanRange, // Maximum range
            ranges = ranges, // The array of measured distances
            intensities = new float[numberOfRays] // No intensities for this scanner (set values if needed)
        };

        // Publish the message
        ros.Publish(topicName, laserScan);
    }
}
